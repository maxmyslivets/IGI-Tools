(defun c:IGI_FIX_Z_FROM_ATTR_SP92 ( / ss ssFiltered i ent vlaObj effName valStr valReal insertionPoint newPoint oldError)
  (vl-load-com)
  (princ "\n=== Перенос значения из атрибута Z в координату Z блока СП_9.2 ===")

  ;; Локальный обработчик ошибок для безопасности транзакций Undo
  (setq oldError *error*)
  (defun *error* (msg)
    (vla-endundomark (vla-get-activedocument (vlax-get-acad-object)))
    (setq *error* oldError)
    (if (not (wcmatch (strcase msg t) "*break*,*cancel*,*exit*"))
      (princ (strcat "\n[Ошибка]: " msg))
    )
    (princ)
  )

  ;; 1. Проверка предварительного выбора (Pickfirst)
  (setq ss (ssget "_I" '((0 . "INSERT") (66 . 1) (2 . "СП_9.2,`*U*"))))

  ;; 2. Если предварительного выбора нет, запрашиваем выбор у пользователя
  (if (null ss)
    (progn
      (princ "\nВыберите блоки СП_9.2 для исправления координаты Z...")
      (setq ss (ssget '((0 . "INSERT") (66 . 1) (2 . "СП_9.2,`*U*"))))
    )
  )

  ;; 3. Обработка набора объектов
  (if ss
    (progn
      (setq ssFiltered (ssadd))
      (setq i 0)

      ;; Начало группы отмены (Undo)
      (vla-startundomark (vla-get-activedocument (vlax-get-acad-object)))

      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq vlaObj (vlax-ename->vla-object ent))
        (setq effName (vla-get-effectivename vlaObj))

        ;; Проверяем, что эффективное имя динамического блока именно "СП_9.2"
        (if (= (strcase effName) (strcase "СП_9.2"))
          (progn
            ;; Ищем атрибут Z
            (foreach att (vlax-invoke vlaObj 'GetAttributes)
              (if (= (strcase (vla-get-tagstring att)) "Z")
                (progn
                  (setq valStr (vla-get-textstring att))
                  (setq valStr (vl-string-translate "," "." valStr)) ;; Замена запятой на точку

                  ;; Проверяем, что в атрибуте действительно число
                  (if (and valStr (/= valStr "") (numberp (distof valStr)))
                    (progn
                      (setq valReal (atof valStr))

                      ;; Получаем текущую точку вставки блока (Variant -> SafeArray -> List)
                      (setq insertionPoint (vlax-safearray->list (vlax-variant-value (vla-get-insertionpoint vlaObj))))

                      ;; Формируем новые координаты (X и Y старые, Z берем из атрибута)
                      (setq newPoint (list (car insertionPoint) (cadr insertionPoint) valReal))

                      ;; Физически перемещаем блок на новую координату Z
                      (vla-put-insertionpoint vlaObj (vlax-3d-point newPoint))

                      ;; Добавляем успешно измененный блок в итоговый набор
                      (ssadd ent ssFiltered)
                    )
                  )
                )
              )
            )
          )
        )
        (setq i (1+ i))
      )

      ;; Завершение группы отмены (Undo)
      (vla-endundomark (vla-get-activedocument (vlax-get-acad-object)))

      ;; 4. Итоги работы и подсветка измененных блоков
      (if (> (sslength ssFiltered) 0)
        (progn
          (sssetfirst nil ssFiltered)
          (princ (strcat "\nУспешно перемещено и выделено блоков: " (itoa (sslength ssFiltered))))
        )
        (princ "\nСреди выбранных объектов не найдено подходящих блоков с заполненным атрибутом Z.")
      )
    )
    (princ "\nБлоки не выбраны.")
  )

  ;; Восстановление стандартного обработчика ошибок
  (setq *error* oldError)
  (princ)
)
