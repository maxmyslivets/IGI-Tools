(defun c:IGI_SelectSP92 ( / *error* effName ssPre ssSelection ssResult i ent vlaObj curName )
  (vl-load-com)
  
  ;; Обработчик ошибок
  (defun *error* (msg)
    (if (not (member msg '("Function cancelled" "quit / exit abort")))
      (princ (strcat "\nОшибка: " msg))
    )
    (princ)
  )

  (setq effName "СП_9.2") ; Имя целевого блока
  (setq ssResult (ssadd)) ; Создаем пустой набор для результата

  ;; 1. Проверяем предварительное выделение (Pickfirst)
  (setq ssPre (ssget "_I" '((0 . "INSERT"))))
  
  (cond
    ;; Если объекты уже были выделены до запуска команды
    (ssPre 
     (setq ssSelection ssPre)
     (sssetfirst nil nil) ; Сбрасываем предварительное выделение для корректной работы
    )
    ;; Если ничего выделено не было — запрашиваем выбор
    (t 
     (princ "\nВыберите объекты на экране [или нажмите Enter для поиска по ВСЕМУ чертежу]: ")
     (setq ssSelection (ssget '((0 . "INSERT"))))
     ;; Если пользователь нажал Enter (выбор пустой) — берем весь чертеж
     (if (null ssSelection)
       (setq ssSelection (ssget "_X" '((0 . "INSERT"))))
     )
    )
  )

  ;; 2. Фильтрация блоков по эффективному имени
  (if ssSelection
    (progn
      (setq i (sslength ssSelection))
      (while (> i 0)
        (setq i (1- i))
        (setq ent (ssname ssSelection i))
        (setq vlaObj (vlax-ename->vla-object ent))
        
        ;; Проверяем, является ли объект блоком и совпадает ли его эффективное имя
        (if (and (vlax-property-available-p vlaObj 'EffectiveName)
                 (= (strcase (vla-get-EffectiveName vlaObj)) (strcase effName)))
          (ssadd ent ssResult)
        )
      )
      
      ;; 3. Вывод результата
      (if (> (sslength ssResult) 0)
        (progn
          (sssetfirst nil ssResult) ; Выделяем и подсвечиваем найденные блоки
          (princ (strcat "\nНайдено и выбрано блоков \"" effName "\": " (itoa (sslength ssResult))))
        )
        (princ (strcat "\nДинамические блоки с именем \"" effName "\" не найдены."))
      )
    )
    (princ "\nОбъекты для анализа не выбраны.")
  )
  (princ)
)

(princ "\nКоманда загружена. Введите SelectSP92 для запуска.")
(princ)
