(defun c:IGI_InsertKolodecAttrBlockText ( / *block-defs* blockNamesFilter ss ent vlaObj effName blkDef attrTags attrMap tag subEnt dxf totalNonZ filledCount lastFilledIdx hasGap maxPos userPos newVal oldError i updatedVals item pair insEnt dxfList newDxf sub prevTag val)
  (vl-load-com)
  (princ "\n=== Вклинивание текста в атрибут блока ===")

  ;; --- Таблица известных динамических блоков и их атрибутов ---
  (setq *block-defs* (list
    (cons "СП_4.1.2.1.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.2.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.3.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.4.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.5.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.7.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.8.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.1.2.9.л" '("Z" "Z1" "Z2" "Z3" "Z4"))
    (cons "СП_4.2.1"     '("Z" "Z1" "Z2"))
    (cons "СП_4.3.1.1"   '("Z" "Z1" "Z2" "Z3"))
    (cons "СП_4.8.5.1"   '("Z" "Z1" "Z2" "Z3" "Z4"))
  ))

  ;; Строка фильтра для ssget
  (setq blockNamesFilter "")
  (foreach def *block-defs*
    (setq blockNamesFilter (strcat blockNamesFilter (car def) ","))
  )
  (setq blockNamesFilter (strcat blockNamesFilter "`*U*"))

  ;; --- Обработчик ошибок ---
  (setq oldError *error*)
  (defun *error* (msg)
    (vla-EndUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))
    (setq *error* oldError)
    (if (not (wcmatch (strcase msg t) "*break*,*cancel*,*exit*,*quit*,*функция отменена*"))
      (princ (strcat "\n[Ошибка]: " msg))
    )
    (princ)
  )

  ;; --- Выбор блока ---
  (if (and (setq ss (ssget "_I" (list (cons 0 "INSERT") (cons 66 1) (cons 2 blockNamesFilter)))) (= (sslength ss) 1))
    (setq ent (ssname ss 0))
    (progn
      (princ "\nВыберите блок: ")
      (setq ss (ssget (list (cons 0 "INSERT") (cons 66 1) (cons 2 blockNamesFilter))))
      (if (and ss (= (sslength ss) 1))
        (setq ent (ssname ss 0))
        (progn
          (princ "\nОшибка: необходимо выбрать ровно один поддерживаемый блок с атрибутами.")
          (exit)
        )
      )
    )
  )

  ;; --- Определяем имя блока через EffectiveName ---
  (setq vlaObj (vlax-ename->vla-object ent))
  (if (= (vla-get-IsDynamicBlock vlaObj) :vlax-true)
    (setq effName (vla-get-EffectiveName vlaObj))
    (setq effName (vla-get-Name vlaObj))
  )
  (if (= (type effName) 'VARIANT)
    (setq effName (vlax-variant-value effName))
  )

  (setq blkDef (assoc effName *block-defs*))
  (if (null blkDef)
    (progn
      (princ (strcat "\nОшибка: блок \"" effName "\" не поддерживается."))
      (exit)
    )
  )
  (setq attrTags (cdr blkDef))

  ;; --- Сбор карты атрибутов через чистый DXF (Тег -> Ename сущности) ---
  (setq attrMap (list))
  (setq subEnt (entnext ent))
  (while (and subEnt (/= (cdr (assoc 0 (entget subEnt))) "SEQEND"))
    (if (= (cdr (assoc 0 (entget subEnt))) "ATTRIB")
      (progn
        (setq tag (strcase (cdr (assoc 2 (entget subEnt)))))
        (setq attrMap (cons (cons tag subEnt) attrMap))
      )
    )
    (setq subEnt (entnext subEnt))
  )

  ;; --- Анализ заполненности Z1..ZN ---
  (setq totalNonZ (1- (length attrTags)))
  (setq i 1)
  (setq filledCount 0)
  (setq lastFilledIdx 0)
  (setq hasGap nil)

  (repeat totalNonZ
    (setq tag (strcase (nth i attrTags)))
    (setq pair (assoc tag attrMap))
    (if pair
      (progn
        (setq val (cdr (assoc 1 (entget (cdr pair)))))
        (if (and val (/= val "") (/= val " "))
          (progn
            (setq filledCount (1+ filledCount))
            (if (> i (1+ lastFilledIdx))
              (setq hasGap t)
            )
            (setq lastFilledIdx i)
          )
        )
      )
    )
    (setq i (1+ i))
  )

  (if (= filledCount totalNonZ)
    (progn (princ "\nОшибка: не осталось свободных атрибутов.") (exit))
  )
  (if hasGap
    (progn (princ "\nОшибка: структура заполненных атрибутов не удовлетворяет условию последовательного заполнения.") (exit))
  )

  ;; --- Расчёт допустимых позиций ---
  (if (= lastFilledIdx 0)
    (setq maxPos 1)
    (setq maxPos (1+ lastFilledIdx))
  )
  (if (> maxPos totalNonZ)
    (setq maxPos totalNonZ)
  )

  ;; --- Запрос позиции ---
  (initget 3)
  (setq userPos (getint (strcat "\nВведите новую позицию (от 1 до " (itoa maxPos) "): ")))
  (while (and userPos (or (< userPos 1) (> userPos maxPos)))
    (initget 3)
    (setq userPos (getint (strcat "\nПозиция должна быть от 1 до " (itoa maxPos) ". Повторите: ")))
  )
  (if (null userPos)
    (progn (princ "\nКоманда отменена.") (exit))
  )

  ;; --- Запрос нового значения ---
  (princ (strcat "\nВведите новое значение для позиции " (itoa userPos) ": "))
  (setq newVal (getstring t))
  (if (or (null newVal) (= newVal ""))
    (progn (princ "\nЗначение не может быть пустым. Команда отменена.") (exit))
  )

  ;; --- Начало Undo-группы ---
  (vla-StartUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; --- Расчет новых значений в оперативной памяти ---
  (setq updatedVals (list))
  (setq i 1)
  (repeat totalNonZ
    (cond
      ((< i userPos)
       (setq tag (strcase (nth i attrTags)))
       (setq updatedVals (cons (cons tag (cdr (assoc 1 (entget (cdr (assoc tag attrMap)))))) updatedVals))
      )
      ((= i userPos)
       (setq tag (strcase (nth i attrTags)))
       (setq updatedVals (cons (cons tag newVal) updatedVals))
      )
      ((> i userPos)
       (setq tag (strcase (nth i attrTags)))
       (setq prevTag (strcase (nth (1- i) attrTags)))
       (setq updatedVals (cons (cons tag (cdr (assoc 1 (entget (cdr (assoc prevTag attrMap)))))) updatedVals))
      )
    )
    (setq i (1+ i))
  )

  ;; --- Обновление DXF-структур атрибутов ---
  (foreach item updatedVals
    (setq insEnt (cdr (assoc (car item) attrMap)))
    (if insEnt
      (progn
        (setq dxfList (entget insEnt))
        (setq newDxf nil)
        (foreach sub dxfList
          (if (= (car sub) 1)
            (setq newDxf (append newDxf (list (cons 1 (cdr item)))))
            (setq newDxf (append newDxf (list sub)))
          )
        )
        (entmod newDxf)
      )
    )
  )

  ;; --- Регенерация графики блока ---
  (entupd ent)

  ;; --- Завершение Undo ---
  (vla-EndUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))
  (princ (strcat "\nЗначение \"" newVal "\" успешно вставлено в позицию " (itoa userPos) ". Остальные сдвинуты."))

  (setq *error* oldError)
  (princ)
)
(princ "\nСкрипт загружен. Команда: IGI_InsertKolodecAttrBlockText")
(princ)
