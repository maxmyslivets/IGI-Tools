(defun c:IGI_InsertKolodecAttrBlockText ( / *block-defs* blockNamesFilter ss ent vlaObj effName
                                     blkDef attrTags attrMap tag val attObj pair
                                     i totalNonZ filledCount lastFilledIdx hasGap
                                     maxPos userPos newVal oldError curVal curObj
                                     nextTag nextObj insTag insObj)
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

  ;; Строка фильтра для ssget (имена + динамические *U*)
  (setq blockNamesFilter "")
  (foreach def *block-defs*
    (setq blockNamesFilter (strcat blockNamesFilter (car def) ","))
  )
  (setq blockNamesFilter (strcat blockNamesFilter "`*U*"))

  ;; --- Обработчик ошибок (с завершением Undo-группы) ---
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
  (if (and (setq ss (ssget "_I" (list (cons 0 "INSERT") (cons 66 1) (cons 2 blockNamesFilter))))
           (= (sslength ss) 1))
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

  ;; --- Определяем имя блока через EffectiveName (для динамических блоков) ---
  (setq vlaObj (vlax-ename->vla-object ent))
  (if (= (vla-get-IsDynamicBlock vlaObj) :vlax-true)
    (setq effName (vla-get-EffectiveName vlaObj))
    (setq effName (vla-get-Name vlaObj))
  )
  ;; vla-get-EffectiveName/Name могут вернуть Variant или STR — приводим к строке
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

  (setq attrTags (cdr blkDef))  ;; ("Z" "Z1" "Z2" ...)

  ;; --- Карта тег -> (значение . VLA-объект атрибута) ---
  (setq attrMap (list))
  (foreach attObj (vlax-invoke vlaObj 'GetAttributes)
    (setq tag (strcase (vla-get-tagstring attObj)))
    (setq val (vla-get-textstring attObj))
    (setq attrMap (cons (cons tag (cons val attObj)) attrMap))
  )

  ;; --- Анализ заполненности Z1..ZN ---
  (setq totalNonZ (1- (length attrTags)))
  (setq i 1)
  (setq filledCount 0)
  (setq lastFilledIdx 0)
  (setq hasGap nil)

  (repeat totalNonZ
    (setq tag (nth i attrTags))
    (setq pair (assoc tag attrMap))
    (setq val (car (cdr pair)))

    (if (and val (/= val "") (/= val " "))
      (progn
        (setq filledCount (1+ filledCount))
        (if (> i (1+ lastFilledIdx))
          (setq hasGap t)
        )
        (setq lastFilledIdx i)
      )
    )
    (setq i (1+ i))
  )

  ;; Все заполнены — ошибка
  (if (= filledCount totalNonZ)
    (progn
      (princ "\nОшибка: не осталось свободных атрибутов.")
      (exit)
    )
  )

  ;; Разрыв в последовательности — ошибка
  (if hasGap
    (progn
      (princ "\nОшибка: структура заполненных атрибутов не удовлетворяет условию последовательного заполнения.")
      (exit)
    )
  )

  ;; --- Расчёт допустимых позиций для вставки ---
  (if (= lastFilledIdx 0)
    (setq maxPos 1)
    (setq maxPos lastFilledIdx)
  )

  ;; --- Запрос позиции ---
  (initget 3)  ;; запрет 0 и отрицательных
  (setq userPos (getint (strcat "\nВведите новую позицию (от 1 до " (itoa maxPos) "): ")))

  (while (and userPos (or (< userPos 1) (> userPos maxPos)))
    (initget 3)
    (setq userPos (getint (strcat "\nПозиция должна быть от 1 до " (itoa maxPos) ". Повторите: ")))
  )

  (if (null userPos)
    (progn
      (princ "\nКоманда отменена.")
      (exit)
    )
  )

  ;; --- Запрос нового значения ---
  (princ (strcat "\nВведите новое значение для позиции " (itoa userPos) ": "))
  (setq newVal (getstring t))

  (if (null newVal)
    (progn
      (princ "\nКоманда отменена.")
      (exit)
    )
  )

  (if (= newVal "")
    (progn
      (princ "\nЗначение не может быть пустым.")
      (exit)
    )
  )

  ;; --- Начало Undo-группы ---
  (vla-StartUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; --- Сдвиг значений: от lastFilledIdx вниз до userPos ---
  (setq i lastFilledIdx)
  (while (>= i userPos)
    (setq curVal (car (cdr (assoc (nth i attrTags) attrMap))))
    (setq nextObj (cdr (cdr (assoc (nth (1+ i) attrTags) attrMap))))

    (if (and curVal nextObj)
      (vla-put-textstring nextObj curVal)
    )

    (setq i (1- i))
  )

  ;; --- Запись нового значения в позицию userPos ---
  (setq insTag (nth userPos attrTags))
  (setq insObj (cdr (cdr (assoc insTag attrMap))))
  (vla-put-textstring insObj newVal)

  ;; --- Обновление блока на экране ---
  (vla-update vlaObj)

  ;; --- Завершение Undo ---
  (vla-EndUndoMark (vla-get-ActiveDocument (vlax-get-acad-object)))

  (princ (strcat "\nЗначение \"" newVal "\" вставлено в позицию " (itoa userPos) ". Остальные сдвинуты."))

  ;; --- Восстановление обработчика ---
  (setq *error* oldError)
  (princ)
)

(princ "\nСкрипт загружен. Команда: IGI_InsertAttrBlockText")
(princ)