"""Собирает статический сайт GitHub Pages без сторонних зависимостей."""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist' / 'website'
PAGES = {'index': 'Главная', 'support': 'Поддержка', 'privacy': 'Конфиденциальность', 'terms': 'Условия'}


def configuration():
    return json.loads((ROOT / 'website' / 'site.json').read_text(encoding='utf-8'))


def config_errors(config):
    problems = []
    for key in ('repository_url', 'site_url', 'support_url'):
        value = config.get(key, '')
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                     and not parsed.password and not any(c.isspace() for c in value))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            problems.append(f'{key}: нужен HTTPS URL без учётных данных')
    if not isinstance(config.get('publisher_name'), str) or not config['publisher_name'].strip():
        problems.append('publisher_name: укажи издателя')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', config.get('updated_on', '')):
        problems.append('updated_on: нужна дата YYYY-MM-DD')
    return problems


def listing_urls(config):
    base = config['site_url'].rstrip('/') + '/'
    return {'websiteURL': base, 'supportURL': base + 'support/',
            'privacyPolicyURL': base + 'privacy/', 'termsOfServiceURL': base + 'terms/'}


def render(config, key):
    prefix = '' if key == 'index' else '../'
    publisher = html.escape(config['publisher_name'])
    repository = html.escape(config['repository_url'], quote=True)
    support = html.escape(config['support_url'], quote=True)
    content = (ROOT / 'website' / 'content' / f'{key}.html').read_text(encoding='utf-8')
    replacements = {
        '{{PUBLISHER}}': publisher,
        '{{UPDATED_ON}}': html.escape(config['updated_on']),
        '{{REPOSITORY_BUTTON}}': f'<a class="button" href="{repository}">Открыть репозиторий ↗</a>',
        '{{SUPPORT_BUTTON}}': f'<a class="button" href="{support}">Открыть GitHub Issues ↗</a>',
    }
    for marker, value in replacements.items():
        content = content.replace(marker, value)
    if '{{' in content or '}}' in content:
        raise ValueError(f'Неразрешённая подстановка: {key}')
    navigation = []
    for page, label in PAGES.items():
        address = prefix + ('index.html' if page == 'index' else page + '/')
        current = ' aria-current="page"' if page == key else ''
        navigation.append(f'<a href="{address}"{current}>{label}</a>')
    navigation = ''.join(navigation)
    title = 'Team Agent Kit — от требований к задаче' if key == 'index' else PAGES[key] + ' — Team Agent Kit'
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="Роли аналитиков, навыки подготовки задач и информация о проекте Team Agent Kit.">
<link rel="icon" href="{prefix}assets/logo.svg" type="image/svg+xml"><link rel="stylesheet" href="{prefix}assets/site.css"></head>
<body><a class="skip" href="#main">К содержимому</a>
<header><div class="shell header-row"><a class="brand" href="{prefix}index.html"><img src="{prefix}assets/logo.svg" alt="" width="42" height="42">Team Agent Kit</a><nav aria-label="Главная навигация">{navigation}</nav></div></header>
<main class="shell" id="main">{content}</main>
<footer class="shell"><div class="footer-row"><div><p>Team Agent Kit · {publisher}</p><p class="published">Инструкции, стандарты и примеры для работы с требованиями.</p></div><nav aria-label="Документы и поддержка">{navigation}</nav></div></footer>
</body></html>
'''


def build():
    config = configuration()
    problems = config_errors(config)
    if problems:
        raise ValueError('; '.join(problems))
    expected = {('index.html' if key == 'index' else key + '/index.html'): render(config, key).encode('utf-8') for key in PAGES}
    expected['assets/site.css'] = (ROOT / 'website' / 'assets' / 'site.css').read_bytes()
    expected['assets/logo.svg'] = (ROOT / 'packaging' / 'assets' / 'logo.svg').read_bytes()
    expected['listing-urls.json'] = (json.dumps(listing_urls(config), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if OUTPUT.is_symlink() or OUTPUT.resolve() != ROOT / 'dist' / 'website':
        raise ValueError('Неожиданный каталог сайта')
    actual = {p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob('*') if p.is_file()}
    if actual - set(expected):
        raise ValueError('В dist/website есть посторонние файлы; автоматическое удаление не выполняется')
    for relative, data in expected.items():
        file = OUTPUT / relative
        if file.is_symlink() or not file.resolve().is_relative_to(OUTPUT.resolve()):
            raise ValueError(f'Недопустимый путь: {relative}')
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    return config, expected


def main():
    try:
        config, files = build()
    except (OSError, ValueError, KeyError) as exc:
        print(f'ОШИБКА: {exc}', file=sys.stderr)
        return 1
    print(f'Сайт: dist/website; файлов: {len(files)}; собран локально')
    print('Планируемые URL (доступность после деплоя ещё не подтверждена):')
    print(json.dumps(listing_urls(config), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
