  ;; Вспомогательная функция парсинга строки по шаблону "минус(нет)-число-текст(нет)"
  ;; Корректно обрабатывает пробелы (например, "-2.48 в.тр. IV")
  (defun parse-z-string (str / len i char sign numStr suffix state)
    ;; Удаляем начальные пробелы, если они есть
    (setq str (vl-string-left-trim " " str))
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
         ;; Пропускаем пробелы после минуса, если они случайно есть
         (while (and (<= i len) (= (substr str i 1) " "))
           (setq i (1+ i))
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
           (setq state 2) ;; Встретили не цифру и не точку (например, пробел или букву) -> начался суффикс
         )
        )

        ;; Состояние 2: сбор оставшегося текста (суффикса)
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
