(defun c:IGI_KolodecCalcZ ( / ss ent attr zVal attrList entData attrTag attrVal sign numStr suffix char i len numVal newVal parsed *error* doc idx ssLen)
  (vl-load-com)

  ;; Ссылка на активный документ для управления отменой
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; НАЧАЛО ОБРАБОТЧИКА ОШИБОК
  (setq *error* (lambda (msg)
    (if (and doc (= (vla-get-ActiveUndoMechanism doc) 1))
      (vla-EndUndoMark doc)
    )
    (if (not (member msg '("Function cancelled" "quit / exit abort")))
      (princ (strcat "\nОшибка: " msg))
    )
    (princ)
  ))
  ;; КОНЕЦ ОБРАБОТЧИКА ОШИБОК

  ;; Вспомогательная функция парсинга строки по шаблону "минус(нет)-число-текст(нет)"
  (defun parse-z-string (str / len i char sign numStr suffix state)
    (setq len (strlen str)
          i 1
          sign 1
          numStr ""
          suffix ""
          state 0 ;; 0 - знак/старт, 1 - сбор числа, 2 - сбор суффикса
    )
    (while (<= i len)
      (setq char (substr str i 1))
      (cond
        ((= state 0)
         (if (= char "-")
           (setq sign -1 i (1+ i))
         )
         (setq state 1)
        )
        ((= state 1)
         (if (wcmatch char "[0-9.]")
           (progn
             (setq numStr (strcat numStr char))
             (setq i (1+ i))
           )
           (setq state 2)
         )
        )
        ((= state 2)
         (setq suffix (substr str i))
         (setq i (1+ len))
        )
      )
    )
    (if (and numStr (/= numStr ""))
      (cons (* sign (distof numStr)) suffix)
      nil
    )
  )

  ;; Выбор блоков пользователя (используем предварительный выбор или запрашиваем новый)
  (if (not (setq ss (ssget "_I" '((0 . "INSERT") (66 . 1)))))
    (progn
      (princ "\nВыберите блоки колодцев с атрибутами: ")
      (setq ss (ssget '((0 . "INSERT") (66 . 1))))
    )
  )

  (if ss
    (progn
      ;; ВКЛЮЧАЕМ МЕТКУ ОТМЕНЫ (одна общая на всю команду)
      (vla-StartUndoMark doc)

      (setq ssLen (sslength ss)
            idx 0)

      ;; Главный цикл по всем выбранным блокам
      (while (< idx ssLen)
        (setq ent (ssname ss idx)
              attr (entnext ent)
              zVal nil
              attrList '())

        ;; Шаг 1: Ищем значение базовой отметки Z для текущего блока
        (while (and attr (= (cdr (assoc 0 (entget attr))) "ATTRIB"))
          (setq entData (entget attr))
          (setq attrTag (strcase (cdr (assoc 2 entData))))
          (setq attrVal (cdr (assoc 1 entData)))

          (if (= attrTag "Z")
            (setq zVal (distof attrVal))
          )
          (setq attrList (cons (cons attrTag attr) attrList))
          (setq attr (entnext attr))
        )

        ;; Шаг 2: Расчет и обновление Z1-Z4 для текущего блока
        (if zVal
          (progn
            (foreach item attrList
              (setq attrTag (car item))
              (setq attr (cdr item))

              (if (member attrTag '("Z1" "Z2" "Z3" "Z4"))
                (progn
                  (setq entData (entget attr))
                  (setq attrVal (cdr (assoc 1 entData)))

                  (if (and attrVal (/= attrVal ""))
                    (progn
                      (setq parsed (parse-z-string attrVal))
                      (if parsed
                        (progn
                          (setq numVal (car parsed))
                          (setq suffix (cdr parsed))

                          ;; Проверка: если разница > 20, пропускаем
                          (if (<= (abs numVal) 20)
                            (progn
                              (setq newVal (rtos (+ zVal numVal) 2 2))
                              (setq newVal (strcat newVal suffix))
                              (setq entData (subst (cons 1 newVal) (assoc 1 entData) entData))
                              (entmod entData)
                            )
                          )
                        )
                      )
                    )
                  )
                )
              )
            )
            (entupd ent) ;; Визуально обновляем блок на экране
          )
          (princ (strcat "\nПредупреждение: У блока " (vl-prin1-to-string ent) " атрибут Z пуст или некорректен."))
        )

        (setq idx (1+ idx)) ;; Переходим к следующему блоку
      )

      ;; ЗАКРЫВАЕМ МЕТКУ ОТМЕНЫ
      (vla-EndUndoMark doc)
      (princ (strcat "\nОбработка завершена. Успешно обработано блоков: " (itoa ssLen)))
    )
    (princ "\nБлоки не выбраны.")
  )
  (princ)
)

(princ "\nСкрипт загружен. Новая команда запуска: KolodecCalcZ")
(princ)
