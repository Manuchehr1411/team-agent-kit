"""Локальная проверка библиотеки. Не исполняет профили и не вызывает модель."""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', 'work', 'dist', '__pycache__', '.codex'}
errors = []


def check(condition, message):
    if not condition:
        errors.append(message)


def local_file(value, owner):
    if not isinstance(value, str):
        check(False, f'{owner}: путь должен быть строкой')
        return
    destination = (ROOT / value).resolve()
    check(destination.is_relative_to(ROOT) and destination.is_file(),
          f'{owner}: недоступный путь {value}')


def validate_yaml(skills):
    try:
        import yaml
    except ImportError:
        check(False, '--yaml требует установленный PyYAML; базовый режим работает без него')
        return 0

    class UniqueLoader(yaml.SafeLoader):
        pass

    def unique_mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if key in result:
                raise ValueError(f'Повтор ключа YAML: {key}')
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                unique_mapping)

    def load(file, content=None):
        try:
            value = yaml.load(content if content is not None else file.read_text(encoding='utf-8'),
                              Loader=UniqueLoader)
            if not isinstance(value, dict):
                raise ValueError('ожидается объект YAML')
            return value
        except (yaml.YAMLError, ValueError, TypeError) as exc:
            check(False, f'{file.relative_to(ROOT)}: {exc}')
            return {}

    for file in skills.values():
        header = file.read_text(encoding='utf-8').split('---\n', 2)[1]
        doc = load(file, header)
        check(isinstance(doc.get('description'), str), f'{file}: description не строка')

    roles = {}
    files = sorted(ROOT.glob('roles/*/skills.yaml'))
    files += sorted(ROOT.glob('profiles/**/*.yaml'))
    docs = {file: load(file) for file in files}
    for file, doc in docs.items():
        check(doc.get('schema_version') == 1, f'{file}: неподдерживаемая версия')
        if file.name == 'skills.yaml':
            role = file.parent.name
            roles[role] = doc
            check(doc.get('role') == role, f'{file}: role не совпадает с каталогом')
            available = doc.get('available_skills', [])
            check(set(available) <= set(skills), f'{file}: неизвестный скилл')
            check(set(doc.get('default_skills', [])) <= set(available),
                  f'{file}: default_skills вне каталога роли')
            local_file(f'roles/{role}/role.md', file)

    for file, doc in docs.items():
        if file.name in {'team.yaml', 'project.yaml'}:
            check(doc.get('id') == file.parent.name, f'{file}: id не совпадает с каталогом')
            offered = doc.get('roles', [])
            check(set(offered) <= set(roles), f'{file}: неизвестная роль')
            check(doc.get('default_role') in offered, f'{file}: default_role вне списка roles')
            policy = doc.get('skills', {})
            enabled, disabled = policy.get('enable', []), policy.get('disable', [])
            check(not (set(enabled) & set(disabled)), f'{file}: конфликт enable/disable')
            check(set(enabled + disabled) <= set(skills), f'{file}: неизвестный ID скилла')
            for reference in doc.get('standards', []):
                local_file(reference, file)
            ids = []
            for source in doc.get('sources', []):
                ids.append(source.get('id'))
                check(source.get('status') in {'approved', 'draft', 'example', 'assumption'},
                      f'{file}: неизвестный статус источника')
                check(bool(source.get('authority')), f'{file}: не указана область источника')
                check(('path' in source) != ('url' in source),
                      f'{file}: источнику нужен ровно один path или url')
                if 'path' in source:
                    local_file(source['path'], file)
            check(len(ids) == len(set(ids)), f'{file}: повтор ID источника')
            if file.name == 'project.yaml':
                local_file(f"profiles/teams/{doc.get('team')}/team.yaml", file)
                local_file(doc.get('issue_types'), file)
        elif file.name == 'issue-types.yaml':
            check(doc.get('project') == file.parent.name, f'{file}: неверный project')
            status = doc.get('status')
            check(status in {'unresolved', 'verified', 'not-applicable'}, f'{file}: неверный status')
            categories = doc.get('categories', {})
            check(set(categories) <= {'development', 'design', 'analysis', 'testing', 'subbug'},
                  f'{file}: неизвестная категория')
            if status == 'verified':
                check(bool(doc.get('metadata_source')), f'{file}: нет источника метаданных')
                for category, mapping in categories.items():
                    check(bool(mapping.get('type_name')) and bool(mapping.get('type_id'))
                          and isinstance(mapping.get('is_subtask'), bool),
                          f'{file}: неполное соответствие {category}')
    return len(files) + len(skills)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yaml', action='store_true', help='Проверить YAML через доступный PyYAML')
    args = parser.parse_args()
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and not (set(p.relative_to(ROOT).parts) & EXCLUDED))
    for file in files:
        check(file.stat().st_size > 0, f'Пустой файл: {file.relative_to(ROOT)}')
    for required in ['README.md', 'AGENTS.md', 'CHANGELOG.md', 'docs/profile-format.md',
                     'checks/scenarios.md', 'checks/results.md']:
        local_file(required, 'структура')

    skills = {}
    for file in ROOT.glob('.agents/skills/*/SKILL.md'):
        content = file.read_text(encoding='utf-8')
        match = re.match(r'\A---\n(.*?)\n---\n', content, re.S)
        check(bool(match), f'{file}: отсутствует frontmatter')
        if not match:
            continue
        name = re.search(r'^name: ([a-z0-9-]+)$', match[1], re.M)
        check(bool(name) and name[1] == file.parent.name and len(name[1]) < 64,
              f'{file}: неверное имя')
        check(bool(re.search(r'^description: \S.+$', match[1], re.M)),
              f'{file}: отсутствует description')
        skills[file.parent.name] = file
    check(bool(skills), 'Не найдено ни одного скилла')

    links = 0
    for file in (p for p in files if p.suffix == '.md'):
        content = file.read_text(encoding='utf-8')
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', content):
            parsed = urlsplit(target.strip('<>'))
            if parsed.scheme or parsed.netloc:
                continue
            links += 1
            destination = (file.parent / unquote(parsed.path)).resolve() if parsed.path else file
            check(destination.is_relative_to(ROOT) and destination.is_file(),
                  f'{file.relative_to(ROOT)}: битая ссылка {target}')
            if parsed.fragment and destination.is_file():
                anchor = parsed.fragment
                # В библиотеке фрагменты используют явные HTML-якоря.
                check(f'id="{anchor}"' in destination.read_text(encoding='utf-8'),
                      f'{file.relative_to(ROOT)}: неизвестный якорь {target}')
    yaml_count = validate_yaml(skills) if args.yaml else 0
    for error in errors:
        print('ОШИБКА:', error)
    print(f'Файлов: {len(files)}; скиллов: {len(skills)}; локальных ссылок: {links}; '
          f'YAML-проверок: {yaml_count}; ошибок: {len(errors)}')
    if not args.yaml:
        print('Синтаксис YAML и связи профилей не проверялись; используйте --yaml.')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
