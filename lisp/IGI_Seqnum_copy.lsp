(vl-load-com)

(defun c:IGI_SEQNUM_COPY ( / startNum currentNum activeDoc ent dxfType sourceObj basePoint textStr len i char numericPart prefix textVal lastEnt copiedObj)
  (princ "\nКопирование текста с автоматическим увеличением нумерации (+1).")
  
  ;; 1. Выбор исходного объекта
  (setq ent (entsel "\nВыберите исходный Текст или МТекст: "))
  (if (not ent)
    (progn (princ "\nНичего не выбрано. Выход.") (exit))
  )
  
  (setq dxfType (cdr (assoc 0 (entget (car ent)))))
  
  (if (member dxfType '("TEXT" "MTEXT"))
    (progn
      (setq sourceObj (vlax-ename->vla-object (car ent)))
      
      ;; 2. Автоматическое определение базовой точки (геометрический центр объекта)
      (vla-GetBoundingBox sourceObj 'minpt 'maxpt)
      (setq minpt (vlax-safearray->list minpt)
            maxpt (vlax-safearray->list maxpt)
            basePoint (list (/ (+ (car minpt) (car maxpt)) 2.0)
                            (/ (+ (cadr minpt) (cadr maxpt)) 2.0)
                            0.0))
      
      ;; 3. Анализ содержимого исходного текста для выявления стартового числа
      (setq textStr (vla-get-TextString sourceObj))
      (setq len (strlen textStr)
            i len
            numericPart ""
            prefix "")
      
      ;; Ищем числовые символы с конца строки
      (while (and (> i 0) (member (setq char (substr textStr i 1)) '("0" "1" "2" "3" "4" "5" "6" "7" "8" "9")))
        (setq numericPart (strcat char numericPart))
        (setq i (1- i))
      )
      
      (if (/= numericPart "")
        (progn
          (setq prefix (substr textStr 1 i))
          (setq startNum (atoi numericPart))
        )
        (progn
          (setq prefix (strcat textStr " "))
          (setq startNum (getint "\nЧисло в тексте не найдено. Введите стартовый номер <1>: "))
          (if (not startNum) (setq startNum 1))
        )
      )
      
      (setq currentNum startNum)
      (setq activeDoc (vla-get-ActiveDocument (vlax-get-acad-object)))
      (vla-StartUndoMark activeDoc)
      
      (princ (strcat "\nШаблон успешно считан. Префикс: \"" prefix "\". Следующий номер: " (itoa (1+ currentNum))))
      
      ;; 4. Интерактивный цикл копирования и последующего переименования
      (setvar "CMDECHO" 0)
      
      (while (= (getvar "CMDACTIVE") 0)
        ;; Запоминаем последний объект в базе чертежа перед копированием
        (setq lastEnt (entlast))
        
        (princ (strcat "\nУкажите точку вставки для номера " (itoa (1+ currentNum)) " (или Нажмите Esc/Enter для выхода): "))
        
        ;; Логика: сначала полностью копируем исходный объект в указанную пользователем точку
        (command "_.copy" (car ent) "" "_non" basePoint "\\")
        
        ;; Если в базе чертежа появился новый объект (пользователь успешно указал точку кликом)
        (if (not (equal (entlast) lastEnt))
          (progn
            ;; Переходим к следующему номеру
            (setq currentNum (1+ currentNum))
            (setq textVal (strcat prefix (itoa currentNum)))
            
            ;; Получаем новый скопированный объект и меняем у него нумерацию
            (setq copiedObj (vlax-ename->vla-object (entlast)))
            (vla-put-TextString copiedObj textVal)
            (vla-Update copiedObj)
          )
          ;; Если объект не появился, значит пользователь отменил команду (нажал Enter или Esc)
          (command)
        )
      )
      
      (vla-EndUndoMark activeDoc)
      (setvar "CMDECHO" 1)
      (princ (strcat "\nНумерация завершена. Остановлено на номере: " (itoa currentNum)))
    )
    (princ "\nОшибка: Выбранный объект не является Текстом или МТекстом!")
  )
  (princ)
)

(princ "\nКоманда загружена. Введите IGI_SEQNUM_COPY для запуска.")
(princ)
