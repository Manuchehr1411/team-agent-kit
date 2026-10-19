"""Проверяет устанавливаемый пакет и ZIP, не меняя настройки клиентов."""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'plugins' / 'team-agent-kit'
LISTING_URLS = ('websiteURL', 'supportURL', 'privacyPolicyURL', 'termsOfServiceURL')


def listing_errors(interface, require_urls=False):
    """Проверка полей листинга; не подтверждает доступность сайта или канала подачи."""
    problems = []
    for field, maximum in (('displayName', 30), ('shortDescription', 30),
                           ('longDescription', 4000), ('developerName', 80)):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            problems.append(f'{field}: нужна непустая строка до {maximum} символов')
    for field in LISTING_URLS:
        value = interface.get(field)
        if value is None and not require_urls:
            continue
        if not isinstance(value, str) or not value.strip():
            problems.append(f'{field}: требуется URL опубликованной страницы')
            continue
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                     and not parsed.password and not any(c.isspace() for c in value)
                     and len(value) <= 1024)
        except ValueError:
            valid = False
        if not valid:
            problems.append(f'{field}: нужен HTTPS URL без учётных данных, до 1024 символов')
    prompts = interface.get('defaultPrompt', [])
    prompts = [prompts] if isinstance(prompts, str) else prompts
    if not isinstance(prompts, list) or len(prompts) > 3 or any(
            not isinstance(value, str) or not value.strip() or len(value) > 128 for value in prompts):
        problems.append('defaultPrompt: не более трёх непустых строк до 128 символов')
    return problems


def markdown_links(folder):
    problems, count = [], 0
    for file in folder.rglob('*.md'):
        for reference in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', file.read_text(encoding='utf-8')):
            parsed = urlsplit(reference.strip('<>'))
            if parsed.scheme or parsed.netloc:
                continue
            count += 1
            target = ((file.parent / unquote(parsed.path)).resolve()
                      if parsed.path else file.resolve())
            if not target.is_relative_to(folder.resolve()) or not target.is_file():
                problems.append(f'{file.relative_to(folder)} → {reference}')
            elif parsed.fragment and f'id="{parsed.fragment}"' not in target.read_text(encoding='utf-8'):
                problems.append(f'{file.relative_to(folder)}: неизвестный якорь {reference}')
    return problems, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submission', action='store_true',
                        help='Дополнительно требовать четыре URL из формы подачи; сетевую доступность не проверяет')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('build_plugin', ROOT / 'scripts' / 'build_plugin.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    try:
        expected = builder.sync(check_only=True)
        portable = json.loads(expected['plugin.json'])
        metadata_problems = listing_errors(portable['extensions']['com.openai']['interface'], args.submission)
        if metadata_problems:
            raise ValueError('; '.join(metadata_problems))
        claude = json.loads(expected['.claude-plugin/plugin.json'])
        compatibility = json.loads(expected['.codex-plugin/plugin.json'])
        identities = {(doc['name'], doc['version']) for doc in (portable, claude, compatibility)}
        if len(identities) != 1:
            raise ValueError('Манифесты описывают разные плагины/версии')
        for field in ('license', 'homepage', 'repository'):
            if any(doc.get(field) != portable.get(field) for doc in (claude, compatibility)):
                raise ValueError(f'Манифесты содержат разные значения {field}')
        if portable.get('license') == 'MIT':
            if expected.get('LICENSE') != (ROOT / 'LICENSE').read_bytes():
                raise ValueError('В пакете отсутствует актуальный текст лицензии')
            if 'docs/licensing.md' not in expected:
                raise ValueError('В пакете отсутствует пояснение лицензии на русском')
        for relative in ('.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json'):
            catalog = json.loads((ROOT / relative).read_text(encoding='utf-8'))
            entry = catalog['plugins'][0]
            source = entry['source']
            target = source['path'] if isinstance(source, dict) else source
            if entry['name'] != portable['name'] or (ROOT / target).resolve() != PACKAGE.resolve():
                raise ValueError(f'Неверное назначение каталога {relative}')
        for name in builder.SKILLS:
            skill = expected[f'skills/{name}/SKILL.md'].decode('utf-8')
            if '(../../AGENTS.md)' not in skill:
                raise ValueError(f'{name}: нет ссылки на инструкции установленного пакета')
        for field in ('logo', 'composerIcon'):
            image = portable['extensions']['com.openai']['interface'][field].removeprefix('./')
            xml = ElementTree.fromstring(expected[image])
            width, height = int(xml.attrib['width']), int(xml.attrib['height'])
            if width != height or width < 48:
                raise ValueError('Иконка должна быть квадратной, от 48 пикселей')
        inventory = json.loads(expected['bundle-manifest.json'])
        for name, digest in inventory['files'].items():
            if hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Не совпадает хеш ресурса {name}')
        archive = ROOT / 'dist' / f"team-agent-kit-{portable['version']}.zip"
        if not archive.is_file():
            raise ValueError('Нет ZIP: сначала выполните python scripts/build_plugin.py')
        problems, links = markdown_links(PACKAGE)
        if problems:
            raise ValueError(f'Битые ссылки установленного пакета: {problems}')

        # Проверка в другом каталоге исключает случайную зависимость от исходников.
        work = ROOT / 'work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='bundle-check-', dir=work) as temporary:
            isolated = Path(temporary).resolve()
            if not isolated.is_relative_to(work.resolve()):
                raise ValueError('Временный каталог находится вне work')
            with zipfile.ZipFile(archive) as bundle:
                if set(bundle.namelist()) != set(expected) or len(bundle.namelist()) != len(expected):
                    raise ValueError('Состав ZIP отличается от проверенного пакета')
                for name, data in expected.items():
                    if bundle.read(name) != data:
                        raise ValueError(f'ZIP содержит другую версию {name}')
                    destination = (isolated / name).resolve()
                    if not destination.is_relative_to(isolated):
                        raise ValueError(f'Путь вне пакета: {name}')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
            extracted_problems, extracted_links = markdown_links(isolated)
            if extracted_problems or extracted_links != links:
                raise ValueError(f'После переноса не работают ссылки: {extracted_problems}')
            # Отрицательная проба: пропажа общего ресурса должна быть обнаружена.
            missing = isolated / 'standards' / 'source-policy.md'
            missing.unlink()
            broken, _ = markdown_links(isolated)
            if not broken:
                raise ValueError('Проверка не обнаружила пропавший общий ресурс')
        print(f'Манифестов: 3; каталогов: 2; скиллов: {len(builder.SKILLS)}; '
              f'ссылок внутри пакета: {links}; ZIP и перенос: проверены; ошибок: 0')
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f'ОШИБКА: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
