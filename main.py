#!/usr/bin/env python3
"""
Скрипт для рекурсивного поиска IPv4-адресов, связанных с DNS-именем.
В отличие от статического парсинга HTML, здесь используется Playwright:
запускается реальный браузер и собираются hostname из фактических сетевых
запросов страницы, включая поздние fetch/XHR после выполнения JavaScript.
"""

import argparse
import ipaddress
import os
import socket
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

# Храним браузеры Playwright рядом с окружением, а не в sandbox-cache.
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
import dns.exception
import dns.resolver

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

MAX_LABEL_LEN = 63
MAX_HOSTNAME_LEN = 253
DEFAULT_WAIT_AFTER_LOAD_MS = 3000
DEFAULT_DNS_NAMESERVERS = ('8.8.8.8', '1.1.1.1')

DNS_SERVER_PRESETS: dict[str, tuple[str, ...]] = {
    'both': DEFAULT_DNS_NAMESERVERS,
    'google': ('8.8.8.8',),
    'cloudflare': ('1.1.1.1',),
}


def is_valid_hostname(host: str) -> bool:
    """Проверяет, что hostname допустим для DNS."""
    if not host or len(host) > MAX_HOSTNAME_LEN:
        return False
    for label in host.split('.'):
        if len(label) > MAX_LABEL_LEN or not label:
            return False
    return True


def normalize_dns_input(value: str) -> str:
    """Извлекает hostname из URL или нормализует голый DNS/host."""
    value = value.strip()
    if not value:
        return ''
    if '://' in value or value.startswith('//'):
        if value.startswith('//'):
            value = 'https:' + value
        parsed = urlparse(value)
        return (parsed.hostname or '').lower()
    return value.split('/')[0].split(':')[0].lower()


def extract_hostname_from_url(raw_url: str) -> str:
    """Возвращает hostname из URL, если он корректен."""
    if not raw_url:
        return ''
    if raw_url.startswith('//'):
        raw_url = 'https:' + raw_url
    parsed = urlparse(raw_url)
    return (parsed.hostname or '').lower()


def resolve_hostname(hostname: str, dns_servers: tuple[str, ...]) -> set[str]:
    """Резолвит DNS-имя во все связанные IPv4 адреса."""
    ips = set()
    host = hostname.split(':')[0] if ':' in hostname else hostname
    if not host or host.startswith('.') or not is_valid_hostname(host):
        return ips

    if _is_ipv4_address(host):
        return {host}

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = list(dns_servers)
    resolver.timeout = 2.0
    resolver.lifetime = 4.0

    try:
        for answer in resolver.resolve(host, 'A'):
            ips.add(answer.address)
    except (dns.exception.DNSException, OSError, UnicodeError):
        pass

    return ips


def _is_ipv4_address(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
    except ValueError:
        return False


def normalize_dns_servers(selection: str, custom_dns_server: str = '') -> tuple[str, ...]:
    """Возвращает список DNS-серверов для резолва по выбору пользователя."""
    normalized = (selection or 'both').strip().lower()
    if normalized in DNS_SERVER_PRESETS:
        return DNS_SERVER_PRESETS[normalized]

    if normalized != 'custom':
        raise ValueError('Недопустимый DNS-сервер')

    custom_dns_server = custom_dns_server.strip()
    if not custom_dns_server:
        raise ValueError('Укажите собственный DNS-сервер')
    if not _is_ipv4_address(custom_dns_server):
        raise ValueError('Собственный DNS-сервер должен быть корректным IPv4-адресом')

    return (custom_dns_server,)


def discover_hostnames(browser, hostname: str, timeout_s: int, wait_after_load_ms: int) -> set[str]:
    """
    Открывает сайт в браузере и собирает hostname из фактических сетевых запросов.
    Это покрывает ресурсы, которые появляются только после выполнения JavaScript.
    """
    discovered = set()
    base_host = hostname.lower()
    timeout_ms = timeout_s * 1000

    context = browser.new_context(
        user_agent=USER_AGENT,
        ignore_https_errors=True,
    )
    page = context.new_page()

    def remember_url(raw_url: str) -> None:
        host = extract_hostname_from_url(raw_url)
        if host and host != base_host and is_valid_hostname(host):
            discovered.add(host)

    page.on('request', lambda request: remember_url(request.url))
    page.on('response', lambda response: remember_url(response.url))

    for candidate in (f'https://{hostname}', f'http://{hostname}'):
        try:
            page.goto(candidate, wait_until='domcontentloaded', timeout=timeout_ms)
            break
        except PlaywrightError:
            continue
    else:
        context.close()
        return discovered

    try:
        page.wait_for_load_state('networkidle', timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass

    # Небольшая пауза даёт шанс отработать поздним JS-запросам.
    if wait_after_load_ms > 0:
        page.wait_for_timeout(wait_after_load_ms)

    # Прокрутка помогает триггернуть lazy-load без взаимодействия пользователя.
    try:
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(1000)
    except PlaywrightError:
        pass

    context.close()
    return discovered


def collect_ipv4_addresses(
    dns: str,
    timeout: int = 10,
    max_depth: int = 1,
    wait_after_load_ms: int = DEFAULT_WAIT_AFTER_LOAD_MS,
    dns_servers: tuple[str, ...] = DEFAULT_DNS_NAMESERVERS,
) -> tuple[str, list[str]]:
    """Возвращает нормализованный hostname и отсортированный список IPv4."""
    hostname = normalize_dns_input(dns)
    if not hostname:
        raise ValueError('DNS-имя не может быть пустым')
    if not is_valid_hostname(hostname):
        raise ValueError(
            f'Недопустимый hostname: метки DNS не более {MAX_LABEL_LEN} символов'
        )

    seen_hosts: set[str] = set()
    to_process: deque[tuple[str, int]] = deque([(hostname, 0)])
    all_ips: set[str] = set()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                while to_process:
                    current, depth = to_process.popleft()
                    if current in seen_hosts:
                        continue
                    seen_hosts.add(current)

                    all_ips.update(resolve_hostname(current, dns_servers))

                    if depth < max_depth:
                        new_hosts = discover_hostnames(
                            browser,
                            current,
                            timeout,
                            wait_after_load_ms,
                        )
                        for host in new_hosts:
                            if host not in seen_hosts and is_valid_hostname(host):
                                to_process.append((host, depth + 1))
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(
            'Не удалось запустить браузер Playwright. Установите Chromium командой: '
            '`PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium`'
        ) from exc

    return hostname, sorted(all_ips)


def build_route_lines(ips: list[str], gateway: str) -> list[str]:
    """Формирует строки route add для найденных IP."""
    return [
        f'route add {ip} mask 255.255.255.255 {gateway}'
        for ip in ips
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Рекурсивно находит IPv4-адреса по DNS через Playwright'
    )
    parser.add_argument(
        'dns',
        metavar='DNS',
        help='DNS-имя или URL (например, example.com или https://www.example.com/)',
    )
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=10,
        help='Таймаут навигации в секундах (по умолчанию: 10)',
    )
    parser.add_argument(
        '-m', '--max-depth',
        type=int,
        default=1,
        help='Максимальная глубина рекурсии по доменам (по умолчанию: 1)',
    )
    parser.add_argument(
        '-w', '--wait-after-load',
        type=int,
        default=DEFAULT_WAIT_AFTER_LOAD_MS,
        help='Сколько ждать после загрузки страницы, мс (по умолчанию: 3000)',
    )
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        help='Файл для вывода IP (по умолчанию — stdout)',
    )
    parser.add_argument(
        '-g', '--gateway',
        default='10.0.0.18',
        help='Шлюз для route add (по умолчанию: 10.0.0.18)',
    )
    args = parser.parse_args()

    try:
        _, result = collect_ipv4_addresses(
            dns=args.dns,
            timeout=args.timeout,
            max_depth=args.max_depth,
            wait_after_load_ms=args.wait_after_load,
        )
    except ValueError as exc:
        parser.error(str(exc))
    except RuntimeError as exc:
        parser.exit(1, f'{exc}\n')

    output = '\n'.join(build_route_lines(result, args.gateway))

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f'Найдено {len(result)} IP-адресов. Результат записан в {args.output}')
    else:
        print(output)


if __name__ == '__main__':
    main()
