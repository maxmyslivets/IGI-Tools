(defun c:IGI_WipeoutCuff ( / acdoc blocks blk obj )
  (vl-load-com)
  (setq acdoc (vla-get-activedocument (vlax-get-acad-object)))
  (setq blocks (vla-get-blocks acdoc))
 
  (vlax-for blk blocks
    (vlax-for obj blk
      (if (= (vla-get-objectname obj) "AcDbWipeout")
        (progn
          ;; Делаем объект полностью невидимым для графического движка
          (vl-catch-all-apply 'vla-put-visible (list obj :vlax-false))
        )
      )
    )
  )
  (vla-regen acdoc acAllViewports)
  (princ "\n[IGI Tools] Маскировки отключены.")
  (princ)
)
(defun c:IGI_WipeoutUncuff ( / acdoc blocks blk obj )
  (vl-load-com)
  (setq acdoc (vla-get-activedocument (vlax-get-acad-object)))
  (setq blocks (vla-get-blocks acdoc))
 
  (vlax-for blk blocks
    (vlax-for obj blk
      (if (= (vla-get-objectname obj) "AcDbWipeout")
        (progn
          ;; Возвращаем базовую видимость маскировкам
          (vl-catch-all-apply 'vla-put-visible (list obj :vlax-true))
        )
      )
    )
  )
  (vla-regen acdoc acAllViewports)
  (princ "\n[IGI Tools] Видимость и работа маскировок восстановлены.")
  (princ)
)
