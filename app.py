from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from main import (
    DEFAULT_WAIT_AFTER_LOAD_MS,
    build_route_lines,
    collect_ipv4_addresses,
    normalize_dns_servers,
)

templates = Jinja2Templates(directory="templates")


class ResolveRequest(BaseModel):
    dns: str = Field(..., description='DNS-имя или URL')
    timeout: int = Field(10, ge=1, description='Таймаут навигации в секундах')
    max_depth: int = Field(1, ge=0, description='Глубина рекурсии по доменам')
    wait_after_load: int = Field(
        DEFAULT_WAIT_AFTER_LOAD_MS,
        ge=0,
        description='Ожидание после загрузки страницы в миллисекундах',
    )
    dns_server: str = Field(
        'both',
        description='DNS-сервер: both, google, cloudflare, custom',
    )
    custom_dns_server: str = Field(
        '',
        description='Собственный DNS-сервер в виде IPv4-адреса',
    )
    format: str = Field(
        'ips',
        description='Формат вывода: ips, wireguard, keenetic',
    )
    gateway: str = Field(
        '',
        description='Шлюз для генерации keenetic route add',
    )


class ResolveResponse(BaseModel):
    hostname: str
    count: int
    ips: list[str]
    wireguard: str
    keenetic: list[str]


app = FastAPI(
    title='Address To IPs API',
    description='API для поиска IPv4 по DNS через Playwright',
    version='0.1.0',
)

app.mount('/static', StaticFiles(directory='static'), name='static')


@app.get('/', response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context={'request': request},
    )


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


def build_wireguard_config(ips: list[str]) -> str:
    """Формирует строку AllowedIPs для WireGuard конфигурации."""
    return ', '.join(f'{ip}/32' for ip in ips)


def build_keenetic_lines(ips: list[str], gateway: str) -> list[str]:
    """Формирует строки для Keenetic route add."""
    return [f'route add {ip} mask 255.255.255.255 {gateway}' for ip in ips]


@app.post('/resolve', response_model=ResolveResponse)
def resolve(request: ResolveRequest) -> ResolveResponse:
    try:
        dns_servers = normalize_dns_servers(
            request.dns_server,
            request.custom_dns_server,
        )
        hostname, ips = collect_ipv4_addresses(
            dns=request.dns,
            timeout=request.timeout,
            max_depth=request.max_depth,
            wait_after_load_ms=request.wait_after_load,
            dns_servers=dns_servers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    wireguard = build_wireguard_config(ips) if request.format == 'wireguard' else ''
    keenetic = build_keenetic_lines(ips, request.gateway) if request.format == 'keenetic' else []
    
    return ResolveResponse(
        hostname=hostname,
        count=len(ips),
        ips=ips,
        wireguard=wireguard,
        keenetic=keenetic,
    )
