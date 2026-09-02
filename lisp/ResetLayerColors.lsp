(defun c:IGI_ResetLayerColors ( / acDoc layersObj layerList layName colVal layObj trueColorObj)
  (vl-load-com)
  (setq acDoc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq layersObj (vla-get-Layers acDoc))
  
  ;; Список соответствия: ("Имя слоя" . "Цвет")
  ;; Индексы AutoCAD задаются числами (7 - белый, 2 - желтый, 3 - зеленый, 6 - фиолетовый).
  ;; RGB цвета задаются строкой вида "R,G,B".
  (setq layerList
    '(
      ("02 Строения и их части" . 7)
      ("15 Дорожная сеть" . 7)
      ("18 Растительность и грунты" . 7)
      ("19 Ограждения" . 7)
    )
  )

  ;; Проходим по всему списку слоев
  (vla-StartUndoMark acDoc)
  (foreach item layerList
    (setq layName (car item))
    (setq colVal (cdr item))
    
    ;; Проверяем, существует ли слой в текущем чертеже
    (if (not (vl-catch-all-error-p (setq layObj (vl-catch-all-apply 'vla-Item (list layersObj layName)))))
      (progn
        ;; Если цвет задан как RGB (строка)
        (if (= (type colVal) 'STR)
          (progn
            (setq trueColorObj (vla-get-TrueColor layObj))
            (vla-put-ColorMethod trueColorObj acColorMethodByRGB)
            ;; Разбиваем строку RGB на три составляющие
            (apply 'vla-setRGB (cons trueColorObj (mapcar 'atoi (string-to-list colVal ","))))
            (vla-put-TrueColor layObj trueColorObj)
          )
          ;; Если цвет задан как индекс AutoCAD (число)
          (vla-put-Color layObj colVal)
        )
      )
    )
  )
  (vla-EndUndoMark acDoc)
  (princ "\nЦвета слоев успешно обновлены!")
  (princ)
)

;; Вспомогательная функция для парсинга RGB строки
(defun string-to-list (str del / pos lst)
  (while (setq pos (vl-string-search del str))
    (setq lst (cons (substr str 1 pos) lst)
          str (substr str (+ pos 2))
    )
  )
  (reverse (cons str lst))
)
