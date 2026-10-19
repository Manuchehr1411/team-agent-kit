# Team Agent Kit

Установочный пакет с двумя ролями и четырьмя скиллами. Подходит для подготовки задач по предоставленным материалам; инструменты и источники подключаются отдельно.

## Начало работы

Укажи роль, скилл, свои источники и желаемый результат. Для реальной задачи учебный профиль не обязателен. Например:

```text
Используй Team Agent Kit, роль business-analyst и скилл describe-task.
Подготовь описание по приведённым ниже требованиям. Верни черновик в чате.
Контекст команды и проекта я пока не задавал.
```

| Скилл | Результат |
| --- | --- |
| describe-task | Соразмерное описание основной задачи |
| decompose-task | Необходимые работы, зависимости и покрытие требований |
| define-dor-dod | Применимые условия готовности и завершения |
| review-task | Независимое ревью без правок по умолчанию |

В Codex выбери установленный скилл через `$`, в ChatGPT — через `@`. В Claude Code используй `/team-agent-kit:describe-task`, `/team-agent-kit:decompose-task`, `/team-agent-kit:define-dor-dod` или `/team-agent-kit:review-task`.

После добавления каталога team-agent-kit плагин устанавливается командами:

```text
codex plugin add team-agent-kit@team-agent-kit
claude plugin install team-agent-kit@team-agent-kit
```

Каталоги marketplace.json поставляются в репозитории рядом с папкой plugins/. ZIP содержит сам плагин, а не весь репозиторий с каталогами установки.

## Роли и профили

Доступны [business-analyst](../roles/business-analyst/role.md) и [system-analyst](../roles/system-analyst/role.md). Ответственность и ограничения задаёт role.md; skills.yaml перечисляет подходящие навыки. Эти файлы не создают агентов и не меняют права инструментов.

Для учебной проверки есть команда [example-team](../profiles/teams/example-team/team.yaml) и проекты [example-project](../profiles/projects/example-project/project.yaml), [catalog-project](../profiles/projects/catalog-project/project.yaml). Не используй их требования в реальных задачах автоматически. Формат собственных профилей: [profile-format.md](../docs/profile-format.md).

При выполнении скилла прочитай инструкции пакета, на которые ссылается его SKILL.md. Режим prepare не записывает задачи в трекер; write требует явного поручения, актуального состояния и метаданных.
