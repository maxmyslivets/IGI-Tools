(defun c:FIX_Z_SP92 ( / ss ssFiltered delta mode hFact hSet i ent vlaObj effName valStr valReal newReal precision)
  (vl-load-com)
  (princ "\n=== Корректировка атрибута Z в блоках СП_9.2 ===")
  
  ;; Выбор режима ввода
  (initget "1 2 V R")
  (setq mode (getkword "\nВыберите режим [1 - Ввод величины / 2 - Расчет по вехе] <1>: "))
  (if (or (null mode) (= mode "1") (= mode "V"))
    (setq mode "1")
    (setq mode "2")
  )
  
  (cond
    ;; Режим 1: Прямой ввод величины поправки
    ((= mode "1")
     (setq delta (getreal "\nВведите величину поправки dZ (например, -0.15 или 0.20): "))
    )
    
    ;; Режим 2: Расчет по высоте вехи
    ((= mode "2")
     (setq hFact (getreal "\nВведите ФАКТИЧЕСКУЮ высоту вехи (м): "))
     (setq hSet  (getreal "\nВведите ЗАДАННУЮ (введенную в прибор) высоту вехи (м): "))
     (if (and hFact hSet)
       (progn
         ;; Формула: dZ = H_заданная - H_фактическая
         (setq delta (- hSet hFact))
         (princ (strcat "\n[Инфо] Рассчитанная поправка dZ = " (rtos delta 2 3) " м."))
       )
     )
    )
  )
  
  ;; Выполнение обработки блоков
  (if (and delta (/= delta 0.0))
    (progn
      (princ "\nВыберите блоки СП_9.2 для изменения...")
      
      ;; Фильтр выбирает блоки с атрибутами: обычные СП_9.2 и динамические анонимные (*U*)
      (setq ss (ssget '((0 . "INSERT") (66 . 1) (2 . "СП_9.2,`*U*"))))
      
      (if ss
        (progn
          (setq ssFiltered (ssadd))
          (setq i 0)
          
          ;; Начало группы отмены (Undo)
          (vla-startundomark (vla-get-activedocument (vlax-get-acad-object)))
          
          (repeat (sslength ss)
            (setq ent (ssname ss i))
            (setq vlaObj (vlax-ename->vla-object ent))
            
            ;; Получение эффективного имени динамического блока
            (setq effName (vla-get-effectivename vlaObj))
            
            ;; Проверка соответствия имени "СП_9.2"
            (if (= (strcase effName) (strcase "СП_9.2"))
              (progn
                ;; Добавляем в итоговый набор для последующего выделения
                (ssadd ent ssFiltered)
                
                ;; Перебор атрибутов через ActiveX
                (foreach att (vlax-invoke vlaObj 'GetAttributes)
                  (if (= (strcase (vla-get-tagstring att)) "Z")
                    (progn
                      (setq valStr (vla-get-textstring att))
                      
                      ;; Замена запятой на точку
                      (setq valStr (vl-string-translate "," "." valStr))
                      (setq valReal (atof valStr))
                      (setq newReal (+ valReal delta))
                      
                      ;; Сохранение исходной точности (знаков после запятой)
                      (setq precision 3)
                      (if (vl-string-search "." valStr)
                        (setq precision (- (strlen valStr) (vl-string-search "." valStr) 1))
                      )
                      (if (< precision 2) (setq precision 2))
                      
                      ;; Запись обновленного значения атрибута
                      (vla-put-textstring att (rtos newReal 2 precision))
                    )
                  )
                )
              )
            )
            (setq i (1+ i))
          )
          
          ;; Завершение группы отмены (Undo)
          (vla-endundomark (vla-get-activedocument (vlax-get-acad-object)))
          
          ;; Выделение только найденных блоков СП_9.2
          (if (> (sslength ssFiltered) 0)
            (progn
              (sssetfirst nil ssFiltered)
              (princ (strcat "\nУспешно обновлено и выделено блоков: " (itoa (sslength ssFiltered))))
            )
            (princ "\nСреди выбранных объектов не найдено блоков с именем СП_9.2.")
          )
        )
        (princ "\nБлоки не выбраны.")
      )
    )
    (princ "\nОбработка отменена: поправка не задана или равна 0.")
  )
  (princ)
)