"""Проверка статических страниц и ссылок перед GitHub Pages, без сети."""
import importlib.util
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'dist' / 'website'


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.headings = [], set(), 0
        self.scripts, self.forms = 0, 0

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if values.get('id'):
            self.ids.add(values['id'])
        if tag == 'h1':
            self.headings += 1
        self.scripts += tag == 'script'
        self.forms += tag == 'form'
        for field in ('href', 'src'):
            if values.get(field):
                self.links.append(values[field])


def main():
    spec = importlib.util.spec_from_file_location('build_website', ROOT / 'scripts' / 'build_website.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    problems, links = [], 0
    config = builder.configuration()
    problems.extend(builder.config_errors(config))
    for key in builder.PAGES:
        relative = 'index.html' if key == 'index' else key + '/index.html'
        file = OUTPUT / relative
        if not file.is_file():
            problems.append(f'Нет страницы {relative}; сначала соберите сайт')
            continue
        content = file.read_text(encoding='utf-8')
        if content != builder.render(config, key):
            problems.append(f'{relative}: страница не соответствует исходникам')
        page = PageParser()
        page.feed(content)
        if page.headings != 1:
            problems.append(f'{relative}: нужен один основной заголовок')
        if page.scripts or page.forms:
            problems.append(f'{relative}: формы/скрипты требуют пересмотра политики данных')
        for reference in page.links:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme != 'https':
                    problems.append(f'{relative}: внешний адрес без HTTPS {reference}')
                continue
            links += 1
            target = (file.parent / unquote(parsed.path)).resolve() if parsed.path else file.resolve()
            if target.is_dir():
                target /= 'index.html'
            if not target.is_relative_to(OUTPUT.resolve()) or not target.is_file():
                problems.append(f'{relative}: ссылка вне сайта или отсутствует {reference}')
            elif parsed.fragment:
                target_page = PageParser()
                target_page.feed(target.read_text(encoding='utf-8'))
                if parsed.fragment not in target_page.ids:
                    problems.append(f'{relative}: отсутствует якорь {reference}')
    for target, source in {
        'assets/site.css': 'website/assets/site.css',
        'assets/logo.svg': 'packaging/assets/logo.svg',
    }.items():
        file = OUTPUT / target
        if not file.is_file() or file.read_bytes() != (ROOT / source).read_bytes():
            problems.append(f'{target}: ресурс отсутствует или устарел')
    urls = OUTPUT / 'listing-urls.json'
    if not urls.is_file() or json.loads(urls.read_text(encoding='utf-8')) != builder.listing_urls(config):
        problems.append('listing-urls.json: адреса не соответствуют конфигурации сайта')
    for problem in problems:
        print('ОШИБКА:', problem)
    print(f'Страниц: {len(builder.PAGES)}; внутренних ссылок и ресурсов: {links}; ошибок: {len(problems)}')
    print('Сетевая доступность URL и публикация не проверялись.')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
