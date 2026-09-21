# Описание стиля кнопок Autodesk Civil 3D (2024-2026)

Спецификация цветовых токенов и правил геометрии интерфейса для ИИ-агента. Предназначена для генерации системных иконок.

---

## Палитра UI-элементов

|                                                              Цвет                                                              | HEX       | Категория                                      |
|:------------------------------------------------------------------------------------------------------------------------------:|:----------|:-----------------------------------------------|
| <span style="background:#D9D9D9; display:block; width:30px; height:20px; border:1px solid #4b5563; border-radius:3px;"></span> | `#D9D9D9` | Основной: Базовый                              |
|              <span style="background:#89CBFA; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#89CBFA` | Основной: **Главный акцент**                   |
|              <span style="background:#808080; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#808080` | Вспомогательный: Нейтральный                   |
|              <span style="background:#666666; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#666666` | Вспомогательный: Контур / Граница              |
|              <span style="background:#82D99F; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#82D99F` | Вспомогательный: Процессы / Действия           |
|              <span style="background:#FFD580; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#FFD580` | Вспомогательный: Модификатор                   |
|              <span style="background:#FF6666; display:block; width:30px; height:20px; border-radius:3px;"></span>              | `#FF6666` | Вспомогательный: Статус / Удаление             |

---

## Дополнительные правила для AI-агента

1. **Стиль:** Flat 2.0 (чистые сплошные цвета, отсутствие градиентов и текстурного шума).
2. **Композиция:** Двухслойная структура. Базовый объект (например, трасса `#D9D9D9`) находится снизу, а слой-модификатор (например, карандаш редактора `#FFD580` или плюс `#89CBFA`) накладывается в правый нижний или левый верхний угол.
