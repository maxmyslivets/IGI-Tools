(defun c:IGI_BringKolodecBlocksToFront ( / *block-defs* blockNamesFilter ss i ent vlaObj effName blkDef validSS oldError)
  (vl-load-com)
  (princ "\n=== Перенос блоков колодцев на верхний уровень ===")

  ;; --- Таблица известных динамических блоков ---
  (setq *block-defs* (list
    (cons "СП_4.1.2.1.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.2.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.3.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.4.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.5.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.7.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.8.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.9.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.2.1"     '("Z" "Z1" "Z2"))
    (cons "СП_4.3.1.1"   '("Z" "Z1" "Z2" "Z3"))
    (cons "СП_4.8.5.1"   '("Z" "Z1" "Z2" "Z3" "Z4"))
  ))

  ;; Строка фильтра для ssget (выбирает точные имена и анонимные блоки *U*)
  (setq blockNamesFilter "")
  (foreach def *block-defs*
    (setq blockNamesFilter (strcat blockNamesFilter (car def) ","))
  )
  (setq blockNamesFilter (strcat blockNamesFilter "`*U*"))

  ;; --- Обработчик ошибок ---
  (setq oldError *error*)
  (defun *error* (msg)
    (vla-EndUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))
    (setq *error* oldError)
    (if (not (wcmatch (strcase msg t) "*break*,*cancel*,*exit*,*quit*,*функция отменена*"))
      (princ (strcat "\n[Ошибка]: " msg))
    )
    (princ)
  )

  ;; --- Начало Undo-группы ---
  (vla-StartUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; --- Выбор всех подходящих вхождений блоков на незаблокированных слоях ---
  (setq ss (ssget "_X" (list (cons 0 "INSERT") (cons 2 blockNamesFilter))))

  (if ss
    (progn
      ;; Создаем новый пустой набор для фильтрации динамических блоков по EffectiveName
      (setq validSS (ssadd))
      (setq i 0)

      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq vlaObj (vlax-ename->vla-object ent))

        ;; Определение реального (эффективного) имени динамического блока
        (if (= (vla-get-IsDynamicBlock vlaObj) :vlax-true)
          (setq effName (vla-get-EffectiveName vlaObj))
          (setq effName (vla-get-Name vlaObj))
        )
        (if (= (type effName) 'VARIANT)
          (setq effName (vlax-variant-value effName))
        )

        ;; Если имя блока есть в нашем списке, добавляем его в итоговый набор
        (if (assoc effName *block-defs*)
          (ssadd ent validSS)
        )
        (setq i (1+ i))
      )

      ;; --- Изменение порядка отображения ---
      (if (> (sslength validSS) 0)
        (progn
          ;; Отключаем вывод лишней информации в консоль при вызове команды
          (vl-cmdf "_.draworder" validSS "" "_Front")
          (princ (strcat "\nУспешно перемещено на передний план блоков: " (itoa (sslength validSS)) "."))
        )
        (princ "\nПоддерживаемые блоки в чертеже не найдены.")
      )
    )
    (princ "\nБлоки для перемещения не обнаружены.")
  )

  ;; --- Завершение Undo ---
  (vla-EndUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq *error* oldError)
  (princ)
)
(princ "\nСкрипт загружен. Команда: IGI_BringKolodecBlocksToFront")
(princ)
