(defun c:INTERP ( / ss i j ent1 ent2 obj1 obj2 bname1 bname2 valid-blocks sorted-blocks p1 p2 z1 z2 get-z dist delta z-start step-dir next-z t-val pt-contour pt-text idivip lines-count mode pt1 pt2 idx)
  (vl-load-com)
  
  ;; Вспомогательная функция для извлечения значения атрибута Z
  (defun get-z (ent / z-val attribs)
    (setq z-val nil)
    (if (= (cdr (assoc 0 (entget ent))) "INSERT")
      (progn
        (setq attribs (vlax-invoke (vlax-ename->vla-object ent) 'GetAttributes))
        (foreach attr attribs
          (if (= (strcase (vla-get-TagString attr)) "Z")
            (setq z-val (distof (vla-get-TextString attr)))
          )
        )
      )
    )
    z-val
  )

  ;; Вспомогательная функция округления для шага горизонталей
  (defun idivip (val size) (fix (/ val size)))

  ;; Функция для интерполяции между двумя конкретными объектами
  (defun do-interpolate (ent1 ent2 / z1 z2 p1 p2 dist delta z-start step-dir next-z t-val pt-contour pt-text)
    (setq z1 (get-z ent1)
          z2 (get-z ent2))
    (if (and z1 z2)
      (progn
        (setq p1 (cdr (assoc 10 (entget ent1))))
        (setq p2 (cdr (assoc 10 (entget ent2))))
        
        ;; Отрисовка соединительной линии
        (entmake (list '(0 . "LINE") (cons 10 p1) (cons 11 p2)))
        
        (setq delta (- z2 z1))
        
        ;; Расчет горизонталей
        (if (/= delta 0.0)
          (progn
            (if (< z1 z2)
              (setq z-start (* 0.5 (idivip (+ z1 0.5) 0.5))
                    step-dir 0.5)
              (setq z-start (* 0.5 (idivip z1 0.5))
                    step-dir -0.5)
            )
            
            (setq next-z z-start)
            
            (while (if (< step-dir 0) (> next-z z2) (< next-z z2))
              (if (if (< step-dir 0) (< next-z z1) (> next-z z1))
                (progn
                  (setq t-val (/ (- next-z z1) delta))
                  (setq pt-contour 
                    (list 
                      (+ (car p1) (* t-val (- (car p2) (car p1))))
                      (+ (cadr p1) (* t-val (- (cadr p2) (cadr p1))))
                      0.0
                    )
                  )
                  ;; Рисуем круг
                  (entmake (list '(0 . "CIRCLE") (cons 10 pt-contour) '(40 . 0.5)))
                  
                  ;; Подпись высоты
                  (setq pt-text (list (+ (car pt-contour) 0.3) (+ (cadr pt-contour) 0.3) 0.0))
                  (entmake (list 
                             '(0 . "TEXT") 
                             (cons 10 pt-text) 
                             (cons 40 0.5) 
                             (cons 1 (rtos next-z 2 2))
                             '(50 . 0.0)
                           ))
                )
              )
              (setq next-z (+ next-z step-dir))
            )
          )
        )
        t ;; Возвращаем истину в случае успешной генерации линии
      )
      nil
    )
  )

  ;; 1. Проверяем предварительно выделенные объекты (Pickfirst)
  (setq ss (ssget "_I"))
  
  ;; 2. Если ничего не выделено, запрашиваем выбор у пользователя
  (if (not ss)
    (progn
      (princ "\nВыделите блоки СП_9.2 на чертеже...")
      (setq ss (ssget '((0 . "INSERT"))))
    )
  )

  ;; 3. Фильтруем выбранные объекты по имени блока
  (setq valid-blocks '())
  (if ss
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (setq bname (vla-get-EffectiveName obj))
        
        (if (= (strcase bname) (strcase "СП_9.2"))
          (setq valid-blocks (cons ent valid-blocks))
        )
        (setq i (1+ i))
      )
    )
  )

  ;; 4. Обработка блоков
  (cond
    ;; Если выбрано ровно 2 блока — обрабатываем сразу
    ((= (length valid-blocks) 2)
      (if (do-interpolate (nth 0 valid-blocks) (nth 1 valid-blocks))
        (princ "\nУспешно построена 1 линия.")
      )
    )
    
    ;; Если выбрано больше 2 блоков — запрашиваем режим
    ((> (length valid-blocks) 2)
      (initget "Цепочка Все _Chain All")
      (setq mode (getkword "\nВыберите режим интерполяции [Цепочка/Все] <Цепочка>: "))
      ;; Если пользователь нажал Enter, по умолчанию ставим "Цепочка"
      (if (not mode) (setq mode "Chain"))
      
      (setq lines-count 0)
      
      ;; РЕЖИМ 1: По цепочке (последовательно слева направо)
      (if (or (= mode "Chain") (= mode "Цепочка"))
        (progn
          ;; Сортировка по координате X
          (setq sorted-blocks 
            (vl-sort valid-blocks 
              '(lambda (e1 e2)
                 (setq pt1 (cdr (assoc 10 (entget e1))))
                 (setq pt2 (cdr (assoc 10 (entget e2))))
                 (if (equal (car pt1) (car pt2) 0.001)
                   (< (cadr pt1) (cadr pt2))
                   (< (car pt1) (car pt2))
                 )
               )
            )
          )
          (setq idx 0)
          (while (< idx (1- (length sorted-blocks)))
            (if (do-interpolate (nth idx sorted-blocks) (nth (1+ idx) sorted-blocks))
              (setq lines-count (1+ lines-count))
            )
            (setq idx (1+ idx))
          )
          (princ (strcat "\nИнтерполяция по цепочке завершена. Обработано линий: " (itoa lines-count)))
        )
        
        ;; РЕЖИМ 2: Все со всеми
        (progn
          (setq i 0)
          (while (< i (1- (length valid-blocks)))
            (setq j (1+ i))
            (while (< j (length valid-blocks))
              (if (do-interpolate (nth i valid-blocks) (nth j valid-blocks))
                (setq lines-count (1+ lines-count))
              )
              (setq j (1+ j))
            )
            (setq i (1+ i))
          )
          (princ (strcat "\nИнтерполяция 'все со всеми' завершена. Обработано линий: " (itoa lines-count)))
        )
      )
    )
    
    ;; Если блоков меньше двух
    (ss
      (princ (strcat "\nОшибка: Найдено блоков СП_9.2: " (itoa (length valid-blocks)) ". Нужно минимум 2."))
    )
    (t
      (princ "\nВыбор отменен.")
    )
  )
  
  (vla-regen (vla-get-activedocument (vlax-get-acad-object)) acAllViewports)
  (princ)
)

(princ "\nСкрипт загружен. Запуск командой: INTERP")
(princ)
