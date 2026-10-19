# Как вносить изменения

Библиотека принимает улучшения методики, примеров и установки. Инструкции и примеры пиши на русском; идентификаторы и имена файлов — на английском. Используй только синтетические или обезличенные данные, которые можно публиковать.

## Источники файлов

- Скиллы редактируются в .agents/skills, роли — в roles, стандарты — в standards. Следуй [AGENTS.md](AGENTS.md).
- Метаданные плагина редактируются в packaging. Каталог plugins/team-agent-kit и marketplace-файлы генерируются сборщиком; не исправляй их вручную.
- Сайт редактируется в website/content и website/assets. HTML в dist/website генерируется и не коммитится.

При изменении поведения добавь или уточни пример, сценарий и фактический результат проверки. Не подменяй поведенческую проверку проверкой ссылок.

## Перед pull request

```text
python scripts/build_plugin.py
python scripts/build_plugin.py --check
python checks/validate.py
python checks/validate_distribution.py --submission
python checks/test_listing_metadata.py
python scripts/build_website.py
python checks/validate_website.py
```

Для дополнительной проверки YAML используй checks/validate.py --yaml, если PyYAML уже установлен. Базовая сборка и CI не требуют сторонних Python-библиотек. В среде с RTK добавляй rtk proxy перед командами.

В pull request объясни проблему, результат и выполненные проверки. Не включай work/, dist/, секреты или личные настройки. Автоматические проверки запускаются для pull request и push в main.

## Выпуск версии

1. Обнови версию одновременно в packaging/plugin.json и packaging/claude-plugin.json. Сохраняй идентификатор team-agent-kit. Для совместимых исправлений увеличивай patch-версию, для новых возможностей — minor; несовместимые изменения отмечай major и объясняй миграцию.
2. Обнови CHANGELOG, текущие инструкции и фактические результаты. Собери пакет и выполни проверки. Добавь сгенерированные файлы plugins/team-agent-kit и каталогов в commit.
3. После push дождись успешного CI для нужного commit. Создай GitHub Release с тегом v&lt;version&gt; на этом commit и приложи team-agent-kit-&lt;version&gt;.zip и соответствующий .zip.sha256 из dist/.
4. Опубликуй сайт ручным workflow Pages и проверь установку, обновление и ссылки на выпуск. Версия сайта берётся из манифеста пакета.

Релиз в GitHub не публикует пакет в каталоге OpenAI. Доступ и ревью этого каталога рассматриваются отдельно. Обращения о безопасности: [SECURITY.md](SECURITY.md). Все изменения распространяются на условиях [MIT](LICENSE); не добавляй чужие материалы без права распространения.
