"""Собирает устанавливаемый пакет и ZIP без сетевых запросов и зависимостей."""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'plugins' / 'team-agent-kit'
SKILLS = ('describe-task', 'decompose-task', 'define-dor-dod', 'review-task')
LINK = re.compile(r'(\[[^\]\n]+\]\()([^)\n]+)(\))')


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def inputs():
    mapping = {}
    trees = {
        **{f'.agents/skills/{name}': f'skills/{name}' for name in SKILLS},
        'roles/business-analyst': 'roles/business-analyst',
        'roles/system-analyst': 'roles/system-analyst',
        'standards': 'standards',
        'profiles/teams/example-team': 'profiles/teams/example-team',
        'profiles/projects/example-project': 'profiles/projects/example-project',
        'profiles/projects/catalog-project': 'profiles/projects/catalog-project',
        'examples': 'examples',
    }
    for source, target in trees.items():
        for file in sorted((ROOT / source).rglob('*')):
            if not file.is_file():
                continue
            if file.is_symlink() or file.suffix not in {'.md', '.yaml'}:
                raise ValueError(f'Непредусмотренный ресурс: {file.relative_to(ROOT)}')
            mapping[file.resolve()] = Path(target) / file.relative_to(ROOT / source)
    single_files = {
        'docs/profile-format.md': 'docs/profile-format.md',
        'docs/licensing.md': 'docs/licensing.md',
        'checks/scenarios.md': 'checks/scenarios.md',
        'checks/results.md': 'checks/results.md',
        'CHANGELOG.md': 'CHANGELOG.md',
        'packaging/plugin-readme.md': 'README.md',
        'packaging/plugin-instructions.md': 'AGENTS.md',
        'packaging/plugin.json': 'plugin.json',
        'packaging/claude-plugin.json': '.claude-plugin/plugin.json',
        'packaging/assets/logo.svg': 'assets/logo.svg',
    }
    if (ROOT / 'LICENSE').is_file():
        single_files['LICENSE'] = 'LICENSE'
    for source, target in single_files.items():
        mapping[(ROOT / source).resolve()] = Path(target)
    return mapping


def render_markdown(file, target, mapping):
    content = file.read_text(encoding='utf-8')

    def replace(match):
        reference = match[2]
        parsed = urlsplit(reference.strip('<>'))
        if parsed.scheme or parsed.netloc:
            return match[0]
        source_target = ((file.parent / unquote(parsed.path)).resolve()
                         if parsed.path else file.resolve())
        if source_target not in mapping:
            raise ValueError(f'Ссылка вне пакета: {file.relative_to(ROOT)} → {reference}')
        relative = os.path.relpath(mapping[source_target], target.parent).replace('\\', '/')
        if parsed.fragment:
            relative += '#' + parsed.fragment
        return match[1] + relative + match[3]

    content = LINK.sub(replace, content)
    if target.name == 'SKILL.md':
        header, body = content[4:].split('\n---\n', 1)
        content = ('---\n' + header + '\n---\n\n'
                   'Перед выполнением прочитай [инструкции установленного пакета](../../AGENTS.md). '
                   'Они задают выбор роли и профиля и работу с ресурсами пакета.\n'
                   + body)
    return content.encode('utf-8')


def expected_files():
    mapping = inputs()
    result = {}
    for source, target in mapping.items():
        if not source.is_file():
            raise ValueError(f'Отсутствует источник: {source.relative_to(ROOT)}')
        result[target.as_posix()] = (render_markdown(source, target, mapping)
                                    if source.suffix == '.md' else source.read_bytes())
    portable = read_json('packaging/plugin.json')
    claude = read_json('packaging/claude-plugin.json')
    if portable['name'] != claude['name'] or portable['version'] != claude['version']:
        raise ValueError('Идентификатор и версия манифестов должны совпадать')
    # Совместимый манифест Codex использует ту же идентичность и UI-метаданные.
    compatibility = {key: portable[key] for key in ('name', 'version', 'description', 'author')}
    compatibility.update({key: portable[key] for key in ('homepage', 'repository', 'license', 'keywords') if key in portable})
    compatibility['skills'] = './skills/'
    compatibility.update(portable['extensions']['com.openai'])
    result['.codex-plugin/plugin.json'] = (json.dumps(compatibility, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    manifest = {
        'schema_version': 1,
        'version': portable['version'],
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(result.items())},
    }
    result['bundle-manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return result


def sync(check_only=False):
    expected = expected_files()
    if PACKAGE.is_symlink() or PACKAGE.resolve() != ROOT / 'plugins' / 'team-agent-kit':
        raise ValueError('Неожиданный путь пакета')
    actual = {file.relative_to(PACKAGE).as_posix(): file for file in PACKAGE.rglob('*') if file.is_file()}
    extra = set(actual) - set(expected)
    if extra:
        raise ValueError(f'В пакете есть посторонние файлы, удаление не выполняется: {sorted(extra)}')
    different = [name for name, data in expected.items()
                 if name not in actual or actual[name].read_bytes() != data]
    if check_only:
        if different:
            raise ValueError(f'Пакет не соответствует исходникам: {different}')
    else:
        for name, data in expected.items():
            file = PACKAGE / name
            if file.is_symlink() or not file.resolve().is_relative_to(PACKAGE.resolve()):
                raise ValueError(f'Недопустимый путь: {name}')
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        version = read_json('packaging/plugin.json')['version']
        archive = ROOT / 'dist' / f'team-agent-kit-{version}.zip'
        archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, data in sorted(expected.items()):
                entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                bundle.writestr(entry, data)
        print(f'ZIP: {archive.relative_to(ROOT)}')
    for source, target in {
        'packaging/openai-marketplace.json': '.agents/plugins/marketplace.json',
        'packaging/claude-marketplace.json': '.claude-plugin/marketplace.json',
    }.items():
        file = ROOT / target
        data = (ROOT / source).read_bytes()
        if file.is_symlink() or not file.resolve().is_relative_to(ROOT):
            raise ValueError(f'Недопустимый путь каталога: {target}')
        if not file.is_file() or file.read_bytes() != data:
            if check_only:
                raise ValueError(f'Каталог установки не соответствует шаблону: {target}')
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
    print(f'Пакет: plugins/team-agent-kit; файлов: {len(expected)}; '
          + ('соответствует исходникам' if check_only else 'собран'))
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Проверить пакет без записи и сборки ZIP')
    args = parser.parse_args()
    try:
        sync(args.check)
    except (OSError, ValueError, KeyError) as exc:
        print(f'ОШИБКА: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
