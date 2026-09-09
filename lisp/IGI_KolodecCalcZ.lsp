(defun c:IGI_KolodecCalcZ ( / ss ent attr zVal attrList entData attrTag attrVal numVal newVal parsed *error* idx ssLen clean-str objAttr format-z-value)
  (vl-load-com)

  ;; НАЧАЛО ОБРАБОТЧИКА ОШИБОК
  (setq *error* (lambda (msg)
    (command "_.UNDO" "_End")
    (if (not (member msg '("Function cancelled" "quit / exit abort")))
      (princ (strcat "\nОшибка: " msg))
    )
    (princ)
  ))
  ;; КОНЕЦ ОБРАБОТЧИКА ОШИБОК

  ;; Функция очистки только крайних пробелов всей исходной строки
  (defun clean-str (str)
    (vl-string-left-trim " " (vl-string-right-trim " " str))
  )

  ;; Вспомогательная функция парсинга строки.
  ;; Возвращает список: (число_как_вещественное . (суффикс . исходная_строка_числа_для_подсчета_знаков))
  (defun parse-z-string (str / len i testStr numVal suffix found lastChar)
    (setq str (clean-str str))
    (setq len (strlen str)
          i len
          found nil)
    (while (and (> i 0) (not found))
      (setq testStr (substr str 1 i))
      (setq numVal (distof testStr))
      (if numVal
        (progn
          (setq lastChar (substr testStr i 1))
          (if (= lastChar " ")
            (setq i (1- i))
            (setq found t
                  suffix (substr str (1+ i)))
          )
        )
        (setq i (1- i))
      )
    )
    ;; Теперь возвращаем еще и testStr (чистую строку числа до парсинга)
    (if found (list numVal suffix testStr) nil)
  )

  ;; Функция динамического форматирования значения на основе исходной точности
  (defun format-z-value (val origNumStr / dotPos precision)
    (setq dotPos (vl-string-search "." origNumStr))
    (if dotPos
      ;; Считаем, сколько символов идет после точки
      (setq precision (- (strlen origNumStr) dotPos 1))
      ;; Если точки вообще не было (целое число), точность принимаем за 0
      (setq precision 0)
    )
    ;; Если знаков меньше 2, принудительно выводим 2 знака. Иначе сохраняем исходную точность.
    (if (< precision 2)
      (rtos val 2 2)
      (rtos val 2 precision)
    )
  )

  ;; Выбор блоков
  (if (not (setq ss (ssget "_I" '((0 . "INSERT") (66 . 1)))))
    (progn
      (princ "\nВыберите блоки колодцев с атрибутами: ")
      (setq ss (ssget '((0 . "INSERT") (66 . 1))))
    )
  )

  (if ss
    (progn
      (command "_.UNDO" "_BEgin")

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
            (setq zVal (distof attrVal))
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
                          (setq numVal (car parsed))
                          (setq suffix (cadr parsed))
                          (setq origNumStr (caddr parsed)) ;; Исходная строка числа (например, "-2.485")

                          ;; Проверка дельты (не более 20)
                          (if (<= (abs numVal) 20)
                            (progn
                              ;; Вычисляем новое значение
                              (setq newVal (+ zVal numVal))
                              ;; Форматируем число по правилу динамической точности
                              (setq newVal (format-z-value newVal origNumStr))
                              ;; Склеиваем с суффиксом (пробелы сохранены)
                              (setq newVal (strcat newVal suffix))

                              (vla-put-TextString objAttr newVal)
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

      (command "_.UNDO" "_End")
      (princ (strcat "\nОбработка завершена. Успешно обработано блоков: " (itoa ssLen)))
    )
    (princ "\nБлоки не выбраны.")
  )
  (princ)
)

(princ "\nСкрипт загружен. Команда запуска: KolodecCalcZ")
(princ)
