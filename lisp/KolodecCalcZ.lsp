(defun c:KolodecCalcZ ( / ss ent attr zVal attrList entData attrTag attrVal sign numStr suffix char i len numVal newVal parsed)
  (vl-load-com)
  
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
        ;; Состояние 0: проверка знака минус
        ((= state 0)
         (if (= char "-")
           (setq sign -1 i (1+ i))
         )
         (setq state 1) ;; Переходим к чтению числа
        )
        
        ;; Состояние 1: чтение цифр и точки
        ((= state 1)
         (if (wcmatch char "[0-9.]")
           (progn
             (setq numStr (strcat numStr char))
             (setq i (1+ i))
           )
           (setq state 2) ;; Встретили не цифру -> начался суффикс
         )
        )
        
        ;; Состояние 2: сбор оставшегося текста
        ((= state 2)
         (setq suffix (substr str i))
         (setq i (1+ len)) ;; Прерываем цикл
        )
      )
    )
    ;; Возвращаем список: (знак * число_как_вещественное . суффикс)
    (if (and numStr (/= numStr ""))
      (cons (* sign (distof numStr)) suffix)
      nil
    )
  )

  ;; Выбор блока пользователя
  (if (and (setq ss (ssget "_I"))
           (= (sslength ss) 1))
    (setq ent (ssname ss 0))
    (progn
      (princ "\nВыберите блок колодца с атрибутами: ")
      (setq ss (ssget '((0 . "INSERT") (66 . 1))))
      (if ss (setq ent (ssname ss 0)))
    )
  )

  (if ent
    (progn
      (setq attr (entnext ent)
            zVal nil
            attrList '())

      ;; Шаг 1: Ищем значение базовой отметки Z
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

      ;; Шаг 2: Расчет и обновление Z1-Z4
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
                        (setq numVal (car parsed))   ;; Получаем число со знаком
                        (setq suffix (cdr parsed))   ;; Получаем текстовый хвостик

                        ;; Проверка: если разница между Z и значением атрибута > 20, пропускаем
                        (if (<= (abs numVal) 20)
                          (progn
                            ;; Складываем с базовым Z и преобразуем в строку с 2 знаками
                            (setq newVal (rtos (+ zVal numVal) 2 2))
                            ;; Склеиваем с исходным суффиксом
                            (setq newVal (strcat newVal suffix))

                            ;; Записываем обратно в блок
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
          (entupd ent)
          (princ "\nАтрибуты колодца успешно пересчитаны.")
        )
        (princ "\nОшибка: Атрибут Z пуст или не содержит корректное число.")
      )
    )
    (princ "\nБлок не выбран.")
  )
  (princ)
)

(princ "\nСкрипт загружен. Новая команда запуска: KolodecCalcZ")
(princ)
