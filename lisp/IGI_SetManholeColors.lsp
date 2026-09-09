(defun c:IGI_SetManholeColors ( / acDoc pfx sfx blkList blkName layout ent count )
  (vl-load-com)
  (setq acDoc (vla-get-ActiveDocument (vlax-get-acad-object)))

  (setq blkList nil)

  ;; Перебираем все возможные комбинации регистра для префикса "СП_" и "сп_"
  ;; и суффикса ".Л" и ".л", чтобы гарантировать совпадение при любом поведении strcase
  (foreach pfx '("СП_" "сп_" "Сп_" "сП_")
    (foreach sfx '(".л" ".Л")

      ;; 1. Блоки БЕЗ суффикса
      (foreach num '("4.1.1.1" "4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4"
                     "4.1.2.5" "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.1"
                     "4.2.2"   "4.3.1.1" "4.8.5.1")
        (setq blkList (cons (strcat pfx num) blkList))
      )

      ;; 2. Блоки С суффиксом
      (foreach num '("4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4" "4.1.2.5"
                     "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.2")
        (setq blkList (cons (strcat pfx num sfx) blkList))
      )

    )
  )

  (vla-StartUndoMark acDoc)
  (setq count 0)

  ;; Перебор пространств чертежа
  (vlax-for layout (vla-get-Layouts acDoc)
    (vlax-for ent (vla-get-Block layout)
      (if (= (vla-get-ObjectName ent) "AcDbBlockReference")
        (progn
          ;; Читаем имя как есть (БЕЗ перевода в нижний регистр через strcase)
          (setq blkName (vla-get-EffectiveName ent))

          ;; Проверяем, есть ли имя в нашем расширенном списке
          (if (member blkName blkList)
            (progn
              (vla-put-Color ent 256) ;; 256 = По слою
              (setq count (1+ count))
            )
          )
        )
      )
    )
  )

  (vla-EndUndoMark acDoc)

  (princ (strcat "\n[IGI Tools] Colors set to ByLayer. Processed: " (itoa count) " blocks."))
  (princ)
)
