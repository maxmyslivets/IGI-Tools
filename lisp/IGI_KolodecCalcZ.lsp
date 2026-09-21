(defun c:IGI_KolodecCalcZ ( / ss ent attr zVal attrList entData attrTag attrVal numVal newValStr parsed *error* idx ssLen clean-str objAttr format-z-value parse-z-string eval-formula)
  (vl-load-com)

  ;; БЕЗОПАСНЫЙ ОБРАБОТЧИК ОШИБОК
  (setq *error* (lambda (msg)
    (vl-catch-all-apply 'command-s '("_.UNDO" "_End"))
    (if (not (member msg '("Function cancelled" "quit / exit abort" "Функция отменена")))
      (princ (strcat "\n[IGI] Ошибка: " msg))
    )
    (princ)
  ))

  ;; Функция очистки крайних пробелов строки
  (defun clean-str (str)
    (vl-string-left-trim " " (vl-string-right-trim " " str))
  )

  ;; Внутренний инфиксный математический парсер строк (Чистый AutoLISP)
  (defun eval-formula (str / tokens i len c item stream lookahead match parse-factor parse-term parse-expr)
    (setq str (vl-string-translate "," "." (clean-str str)))

    ;; Лексический анализатор: разбиваем строку на токены
    (setq tokens '() i 1 len (strlen str) item "")
    (while (<= i len)
      (setq c (substr str i 1))
      (if (vl-string-search c "0123456789.")
        (setq item (strcat item c))
        (progn
          (if (/= item "") (setq tokens (cons (distof item) tokens) item ""))
          (if (vl-string-search c "+-*/()")
            (setq tokens (cons c tokens))
          )
        )
      )
      (setq i (1+ i))
    )
    (if (/= item "") (setq tokens (cons (distof item) tokens)))
    (setq stream (reverse tokens))
    (setq lookahead (car stream))

    ;; Обычные локальные функции через defun вместо ламбд (решает проблему неверной функции)
    (defun match (token)
      (if (= lookahead token)
        (setq stream (cdr stream) lookahead (car stream))
      )
    )

    (defun parse-factor ( / res)
      (cond
        ((numberp lookahead)
         (setq res lookahead)
         (setq stream (cdr stream) lookahead (car stream))
         res)
        ((= lookahead "-")
         (match "-")
         (* -1.0 (parse-factor)))
        ((= lookahead "+")
         (match "+")
         (parse-factor))
        ((= lookahead "(")
         (match "(")
         (setq res (parse-expr))
         (match ")")
         res)
        (t 0.0)
      )
    )

    (defun parse-term ( / val nextVal op)
      (setq val (parse-factor))
      (while (member lookahead '("*" "/"))
        (setq op lookahead)
        (setq stream (cdr stream) lookahead (car stream))
        (setq nextVal (parse-factor))
        (if (= op "*")
          (setq val (* val nextVal))
          (if (/= nextVal 0.0) (setq val (/ val nextVal)) (setq val 0.0))
        )
      )
      val
    )

    (defun parse-expr ( / val nextVal op)
      (setq val (parse-term))
      (while (member lookahead '("+" "-"))
        (setq op lookahead)
        (setq stream (cdr stream) lookahead (car stream))
        (setq nextVal (parse-term))
        (if (= op "+")
          (setq val (+ val nextVal))
          (setq val (- val nextVal))
        )
      )
      val
    )

    ;; Безопасный запуск вычисления главного выражения
    (if stream
      (vl-catch-all-apply 'parse-expr)
      0.0
    )
  )

  ;; Функция точечного разделения математики от текста
  (defun parse-z-string (str / len i c allowed formula partSuffix found numVal)
    (setq str (clean-str str))
    (setq len (strlen str) i 1
          allowed "0123456789.-+*/(),"
          formula "" partSuffix "" found nil)

    (while (<= i len)
      (setq c (substr str i 1))
      (if (and (not found) (vl-string-search c allowed))
        (setq formula (strcat formula c))
        (setq found t partSuffix (strcat partSuffix c))
      )
      (setq i (1+ i))
    )

    (while (and (> (strlen formula) 0) (member (substr formula (strlen formula) 1) '("+" "-" "*" "/")))
      (setq partSuffix (strcat (substr formula (strlen formula) 1) partSuffix))
      (setq formula (substr formula 1 (1- (strlen formula))))
    )

    (if (/= formula "")
      (progn
        (setq numVal (eval-formula formula))
        (if (numberp numVal)
          (list numVal partSuffix formula)
          nil
        )
      )
      nil
    )
  )

  ;; Функция динамического форматирования значения на основе исходной точности формулы
  (defun format-z-value (val origNumStr / dotPos precision calcPart i)
    (setq dotPos (vl-string-search "." origNumStr))
    (if dotPos
      (progn
        (setq calcPart (substr origNumStr (1+ dotPos)))
        (setq i 1 precision 0)
        (while (and (<= i (strlen calcPart)) (vl-string-search (substr calcPart i 1) "0123456789"))
          (setq precision (1+ precision) i (1+ i))
        )
      )
      (setq precision 0)
    )
    (if (< precision 2) (setq precision 2))
    (rtos val 2 precision)
  )

  ;; Выбор блоков с атрибутами (с поддержкой предварительного выбора)
  (if (not (setq ss (ssget "_I" '((0 . "INSERT") (66 . 1)))))
    (progn
      (princ "\nВыберите блоки колодцев с атрибутами: ")
      (setq ss (ssget '((0 . "INSERT") (66 . 1))))
    )
  )

  (if ss
    (progn
      (command-s "_.UNDO" "_BEgin")

      (setq ssLen (sslength ss) idx 0)

      (while (< idx ssLen)
        (setq ent (ssname ss idx)
              attr (entnext ent)
              zVal nil
              attrList '())

        ;; Шаг 1: Собираем атрибуты и ищем базовый Z
        (while (and attr (= (cdr (assoc 0 (entget attr))) "ATTRIB"))
          (setq objAttr (vlax-ename->vla-object attr))
          (setq attrTag (strcase (vla-get-TagString objAttr)))
          (setq attrVal (vla-get-TextString objAttr))

          (if (= attrTag "Z")
            (setq zVal (distof (vl-string-translate "," "." attrVal)))
          )

          (setq attrList (cons (cons attrTag objAttr) attrList))
          (setq attr (entnext attr))
        )

        ;; Шаг 2: Расчет и обновление Z1-Z4
        (if zVal
          (progn
            (foreach item attrList
              (setq attrTag (car item))
              (setq objAttr (cdr item))

              (if (member attrTag '("Z1" "Z2" "Z3" "Z4"))
                (progn
                  (setq attrVal (vla-get-TextString objAttr))

                  (if (and attrVal (/= attrVal ""))
                    (progn
                      (setq parsed (parse-z-string attrVal))
                      (if parsed
                        (progn
                          (setq numVal (car parsed))       ;; Чистый внутренний математический расчет
                          (setq suffix (cadr parsed))       ;; Текст хвостика
                          (setq formulaStr (caddr parsed))  ;; Строка формулы

                          ;; Проверка дельты (не более 20 метров от Z)
                          (if (<= (abs numVal) 20)
                            (progn
                              (setq newVal (+ zVal numVal))
                              (setq newValStr (format-z-value newVal formulaStr))

                              ;; Вывод чистого математического лога в консоль
                              (if (= (substr formulaStr 1 1) "-")
                                (princ (strcat "\n[Лог пересчета] Атрибут " attrTag ": " (rtos zVal 2 2) formulaStr "=" newValStr))
                                (princ (strcat "\n[Лог пересчета] Атрибут " attrTag ": " (rtos zVal 2 2) "+" formulaStr "=" newValStr))
                              )

                              (setq newValStr (strcat newValStr suffix))
                              (vla-put-TextString objAttr newValStr)
                            )
                          )
                        )
                      )
                    )
                  )
                )
              )
            )
          )
          (princ (strcat "\nПропущено: У блока " (vl-prin1-to-string ent) " отсутствует или некорректен атрибут Z."))
        )
        (setq idx (1+ idx))
      )

      (command-s "_.UNDO" "_End")
      (princ (strcat "\nОбработка завершена. Успешно обработано блоков: " (itoa ssLen)))
    )
    (princ "\nБлоки не выбраны.")
  )
  (princ)
)

(princ "\nСкрипт загружен. Команда запуска: KolodecCalcZ")
(princ)
