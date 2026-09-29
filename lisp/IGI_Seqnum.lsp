(vl-load-com)

(defun c:IGI_SEQNUM ( / startNum currentNum activeDoc ent dxfType textObj err)
  (princ "\nПоследовательная нумерация текста по порядку выбора.")
  
  ;; Запрос стартового номера
  (setq startNum (getint "\nВведите стартовый номер <1>: "))
  (if (not startNum) (setq startNum 1))
  (setq currentNum startNum)
  
  (setq activeDoc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (vla-StartUndoMark activeDoc)
  
  ;; Цикл поштучного выбора объектов
  (while (setq ent (entsel (strcat "\nВыберите Текст или МТекст для номера " (itoa currentNum) " (или Enter для выхода): ")))
    (setq dxfType (cdr (assoc 0 (entget (car ent)))))
    
    (if (member dxfType '("TEXT" "MTEXT"))
      (progn
        ;; Получаем COM-объект для безопасного изменения текста
        (setq textObj (vlax-ename->vla-object (car ent)))
        
        ;; Попытка изменить текст
        (setq err (vl-catch-all-apply 'vla-put-TextString (list textObj (itoa currentNum))))
        
        (if (vl-catch-all-error-p err)
          (princ "\nОшибка: Не удалось изменить объект.")
          (progn
            ;; Переходим к следующему номеру, если изменение прошло успешно
            (vla-Update textObj)
            (setq currentNum (1+ currentNum))
          )
        )
      )
      (princ "\nОшибка: Выбранный объект не является Текстом или МТекстом!")
    )
  )
  
  (vla-EndUndoMark activeDoc)
  (princ (strcat "\nНумерация завершена. Остановлено на номере: " (itoa currentNum)))
  (princ)
)

(princ "\nКоманда загружена. Введите SEQNUM для запуска.")
(princ)
