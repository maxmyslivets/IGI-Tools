# Цвета слоёв и блоков

Инструменты для назначения и сброса цветов служебных слоёв и блоков канализационных колодцев.

---

## <img src="/icons/IGI_SetLayerColors.svg" style="height:24px; vertical-align:middle"> IGI_SetLayerColors — установка цветов служебных слоёв

Назначает принятые условные цвета слоям:

| Слой | Цвет | Индекс |
|------|------|--------|
| 02 Строения и их части | Красный | 4 |
| 15 Дорожная сеть | Зелёный | 3 |
| 18 Растительность и грунты | Фиолетовый | 6 |
| 19 Ограждения | Жёлтый | 2 |

1. Введите `IGI_SetLayerColors`, нажмите Enter.
2. Цвета указанных слоёв обновятся, консоль выведет подтверждение.

---

## <img src="/icons/IGI_ResetLayerColors.svg" style="height:24px; vertical-align:middle"> IGI_ResetLayerColors — сброс цветов слоёв на белый

Сбрасывает цвета тех же служебных слоёв (02, 15, 18, 19) на белый (индекс 7).

1. Введите `IGI_ResetLayerColors`, нажмите Enter.

---

## <img src="/icons/IGI_SetManholeColors.svg" style="height:24px; vertical-align:middle"> IGI_SetManholeColors — цвет блоков колодцев «По слою»

Устанавливает блокам канализационных колодцев (СП_4.1.1.1, СП_4.1.2.x, СП_4.2.x, СП_4.3.1.1, СП_4.8.5.1 и их варианты с суффиксом `.л`) свойство Color = **По слою** (ByLayer).

1. Введите `IGI_SetManholeColors`, нажмите Enter.
2. Плагин найдет все блоки колодцев в чертеже и установит им цвет по слою.
3. В консоли отобразится количество обработанных блоков.

---

## <img src="/icons/IGI_ResetManholeColors.svg" style="height:24px; vertical-align:middle"> IGI_ResetManholeColors — цвет блоков колодцев «По блоку»

Устанавливает тем же блокам колодцев свойство Color = **По блоку** (ByBlock).

1. Введите `IGI_ResetManholeColors`, нажмите Enter.

---

## Связанные страницы

- [Работа с колодцами](/guide/manholes)
- [Очистка и обслуживание](/guide/maintenance)