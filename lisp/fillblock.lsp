;; =========================================================================
;; Автоматическая расстановка блоков в контуре (Шахматная / Случайная / Сетка)
;; Команда для запуска в AutoCAD: FILLBLOCK
;; =========================================================================

(vl-load-com)

(defun c:FILLBLOCK ( / ent blkName dx dy dyStep mode row col x y insertPt insertIt
                        minPt maxPt minX minY maxX maxY vertices count blkEnt
                        xOffset randX randY jitter doc spc blkObj scaleX scaleY scaleZ
                        rotRad blkLayer blkColor blkLtype blkLscale blkLweight newBlk)

  ;; Вспомогательная функция: Получение имени блока (поддержка динамических блоков)
  (defun get-blk-name (obj)
    (if (vlax-property-available-p obj 'EffectiveName)
      (vla-get-EffectiveName obj)
      (vla-get-Name obj)
    )
  )

  ;; Вспомогательная функция: Получение вершин LWPOLYLINE
  (defun get-lwvertices (e / eData)
    (setq eData (entget e))
    (mapcar 'cdr (vl-remove-if-not '(lambda (x) (= (car x) 10)) eData))
  )

  ;; Вспомогательная функция: Проверка попадания точки в полигон (Ray-casting)
  (defun pt-in-poly (pt pts / x y count i j p1 p2 x1 y1 x2 y2)
    (setq x (car pt) y (cadr pt))
    (setq count 0 i 0 j (1- (length pts)))
    (while (< i (length pts))
      (setq p1 (nth i pts) p2 (nth j pts))
      (setq x1 (car p1) y1 (cadr p1) x2 (car p2) y2 (cadr p2))
      (if (and (or (and (<= y1 y) (< y y2))
                   (and (<= y2 y) (< y y1)))
               (< x (+ x1 (/ (* (- y y1) (- x2 x1)) (- y2 y1)))))
        (setq count (1+ count))
      )
      (setq j i)
      (setq i (1+ i))
    )
    (= (rem count 2) 1)
  )

  ;; Вспомогательная функция: Генератор случайных чисел от 0.0 до 1.0
  (defun rand ()
    (if (null *seed*) (setq *seed* (getvar "DATE")))
    (setq *seed* (rem (+ (* *seed* 15625) 22221) 65536))
    (/ *seed* 65536.0)
  )

  (princ "\n--- Расстановка блоков в контуре ---")

  ;; 1. Выбор контура
  (setq ent nil)
  (while (not ent)
    (setq ent (car (entsel "\nВыберите замкнутый контур (Полилинию): ")))
    (if ent
      (if (not (wcmatch (cdr (assoc 0 (entget ent))) "*POLYLINE*"))
        (progn 
          (princ "\nОшибка: Объект должен быть полилинией!") 
          (setq ent nil)
        )
      )
    )
  )

  ;; 2. Прямой выбор блока мышью с чертежа
  (setq blkName nil blkObj nil)
  (while (not blkName)
    (setq blkEnt (car (entsel "\nВыберите образец блока на чертеже: ")))
    (if blkEnt
      (if (= (cdr (assoc 0 (entget blkEnt))) "INSERT")
        (progn
          (setq blkObj (vlax-ename->vla-object blkEnt))
          (setq blkName (get-blk-name blkObj))
          
          ;; Считывание геометрических и оформляющих свойств образца
          (setq scaleX     (vla-get-XScaleFactor blkObj)
                scaleY     (vla-get-YScaleFactor blkObj)
                scaleZ     (vla-get-ZScaleFactor blkObj)
                rotRad     (vla-get-Rotation blkObj)
                blkLayer   (vla-get-Layer blkObj)
                blkColor   (vla-get-Color blkObj)
                blkLtype   (vla-get-Linetype blkObj)
                blkLscale  (vla-get-LinetypeScale blkObj)
                blkLweight (vla-get-LineWeight blkObj))
        )
        (princ "\nОшибка: Выбранный объект не является блоком!")
      )
    )
  )

  ;; 3. Расчет и расстановка
  (if (and blkName (tblsearch "BLOCK" blkName))
    (progn
      ;; Единый запрос интервала (шаг по X и Y равны)
      (setq dx (getdist "\nУкажите интервал (шаг по X и Y) <1000>: "))
      (if (not dx) (setq dx 1000.0))
      (setq dy dx)

      ;; Выбор режима
      (initget "Шахматный СЕтка СЛучайный")
      (setq mode (getkword "\nВыберите порядок [Шахматный/СЕтка/СЛучайный] <Шахматный>: "))
      (if (null mode) (setq mode "Шахматный"))

      ;; Шаг по Y для шахматного порядка = dy / 2
      (if (= mode "Шахматный")
        (setq dyStep (/ dy 2.0))
        (setq dyStep dy)
      )

      ;; Габариты контура
      (vla-getboundingbox (vlax-ename->vla-object ent) 'minPt 'maxPt)
      (setq minPt (vlax-safearray->list minPt)
            maxPt (vlax-safearray->list maxPt))
      (setq minX (car minPt) minY (cadr minPt)
            maxX (car maxPt) maxY (cadr maxPt))

      (setq vertices (get-lwvertices ent))

      ;; Инициализация пространств AutoCAD
      (setq doc (vla-get-activedocument (vlax-get-acad-object))
            spc (vla-get-block (vla-get-activelayout doc)))

      (setvar "CMDECHO" 0)
      (vla-startundomark doc)

      (setq row 0 count 0 y minY)

      ;; Обход контура по рядам
      (while (<= y maxY)

        ;; В шахматном режиме нечетный ряд сдвигается на dx / 2
        (if (= mode "Шахматный")
          (if (= (rem row 2) 1)
            (setq xOffset (/ dx 2.0))
            (setq xOffset 0.0)
          )
          (setq xOffset 0.0)
        )

        (setq x (+ minX xOffset))

        (while (<= x maxX)
          (setq insertIt nil)

          (cond
            ;; Режим: Сетка и Шахматный
            ((or (= mode "СЕтка") (= mode "Шахматный"))
             (setq insertPt (list x y 0.0))
             (setq insertIt (pt-in-poly insertPt vertices)))

            ;; Режим: Случайный (Стратифицированное смещение)
            ((= mode "СЛучайный")
             (setq jitter 0.7) ;; Коэффициент разброса
             (setq randX (+ x (* dx 0.5) (* (- (rand) 0.5) dx jitter))
                   randY (+ y (* dy 0.5) (* (- (rand) 0.5) dy jitter))
                   insertPt (list randX randY 0.0))
             (setq insertIt (pt-in-poly insertPt vertices)))
          )

          ;; Вставка блока с полным переносом всех свойств
          (if insertIt
            (progn
              (setq newBlk (vla-InsertBlock spc (vlax-3d-point insertPt) blkName scaleX scaleY scaleZ rotRad))
              
              (vla-put-Layer newBlk blkLayer)
              (vla-put-Color newBlk blkColor)
              (vla-put-Linetype newBlk blkLtype)
              (vla-put-LinetypeScale newBlk blkLscale)
              (vla-put-LineWeight newBlk blkLweight)

              (setq count (1+ count))
            )
          )

          (setq x (+ x dx))
        )
        (setq row (1+ row) y (+ y dyStep))
      )

      (vla-endundomark doc)
      (setvar "CMDECHO" 1)

      (princ (strcat "\nГотово! Расставлено блоков: " (itoa count)))
    )
    (princ "\nОтмена: Блок не был инициализирован.")
  )
  (princ)
)

(princ "\nСкрипт обновлен. Введите FILLBLOCK для запуска.")
(princ)