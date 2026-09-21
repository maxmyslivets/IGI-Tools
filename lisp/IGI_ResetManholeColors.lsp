(defun c:IGI_ResetManholeColors ( / acDoc pfx sfx blkList blkName layout ent count )
  (vl-load-com)
  (setq acDoc (vla-get-ActiveDocument (vlax-get-acad-object)))

  (setq blkList nil)

  ;; Перебираем все возможные комбинации регистра для префикса и суффикса,
  ;; чтобы гарантировать стопроцентное совпадение в любой версии AutoCAD.
  (foreach pfx '("СП_" "сп_" "Сп_" "сП_")
    (foreach sfx '(".л" ".Л")

      ;; 1. Генерируем имена для блоков БЕЗ суффикса
      (foreach num '("4.1.1.1" "4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4"
                     "4.1.2.5" "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.1"
                     "4.2.2"   "4.3.1.1" "4.8.5.1")
        (setq blkList (cons (strcat pfx num) blkList))
      )

      ;; 2. Генерируем имена для блоков С суффиксом ".л"
      (foreach num '("4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4" "4.1.2.5"
                     "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.2")
        (setq blkList (cons (strcat pfx num sfx) blkList))
      )

    )
  )

  (vla-StartUndoMark acDoc)
  (setq count 0)

  ;; Перебор всех пространств чертежа (Модель и Листы)
  (vlax-for layout (vla-get-Layouts acDoc)
    (vlax-for ent (vla-get-Block layout)
      (if (= (vla-get-ObjectName ent) "AcDbBlockReference")
        (progn
          ;; Читаем имя как есть, без принудительного изменения регистра
          (setq blkName (vla-get-EffectiveName ent))

          ;; Сравниваем имя со списком комбинаций
          (if (member blkName blkList)
            (progn
              (vla-put-Color ent 0) ;; 0 = По блоку (ByBlock)
              (setq count (1+ count))
            )
          )
        )
      )
    )
  )

  (vla-EndUndoMark acDoc)

  (princ (strcat "\n[IGI Tools] Colors reset to ByBlock. Processed: " (itoa count) " blocks."))
  (princ)
)
