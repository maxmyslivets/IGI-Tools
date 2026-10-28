(defun igi-insert-sp92 (x y elev / ms bobj dynProps prop propName attribs attr res)
  (vl-load-com)
  (if (not igi_em_doc)
    (setq igi_em_doc (vla-get-ActiveDocument (vlax-get-acad-object))))
  (if (not (tblsearch "BLOCK" "СП_9.2"))
    (progn (princ "\n[IGI Tools] Блок СП_9.2 не определён.") nil)
    (progn
      (vla-StartUndoMark igi_em_doc)
      (setq res
        (vl-catch-all-apply
          '(lambda ()
             (setq ms (vla-get-ModelSpace igi_em_doc))
             (setq bobj (vla-InsertBlock ms (vlax-3d-point x y elev) "СП_9.2" 0.5 0.5 0.5 0.0))
             (vla-put-Color bobj 0)

             ;; Динамические свойства
             (if (= (vla-get-IsDynamicBlock bobj) :vlax-true)
               (progn
                 (setq dynProps (vlax-safearray->list (vlax-variant-value (vla-GetDynamicBlockProperties bobj))))
                 (foreach prop dynProps
                   (setq propName (vla-get-PropertyName prop))
                   (cond
                     ((= (strcase propName) (strcase "Положение X"))
                      (vlax-put-property prop 'Value 0.0))
                     ((= (strcase propName) (strcase "Положение Y"))
                      (vlax-put-property prop 'Value -0.65))
                   )
                 )
               )
             )

             ;; Атрибут Z
             (setq attribs (vlax-invoke bobj 'GetAttributes))
             (foreach attr attribs
               (if (= (strcase (vla-get-TagString attr)) "Z")
                 (vla-put-TextString attr (rtos elev 2 2))
               )
             )

             T
           )
        )
      )
      (vla-EndUndoMark igi_em_doc)
      (if (vl-catch-all-error-p res)
        (progn (princ (strcat "\n[IGI Tools] Ошибка вставки блока СП_9.2: " (vl-catch-all-error-message res))) nil)
        res
      )
    )
  )
)
