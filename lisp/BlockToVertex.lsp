(defun c:block2vertex ( / ss1 ss2 blk selPl selBlk ptlist pt)
    (setq selPl (car (nentsel "\nSelect polyline: ")))
    (setq selBlk (car (nentsel "\nSelect block reference: ")))
    (if (and selPl selBlk)
	(prompt "\nselPl selBlk.")
        (progn
            (setq ss1 (ssget "_X" (list (cons 0 "VERTEX") (cons 8 (cdr (assoc 8 (entget selPl)))))))
            (repeat (sslength ss1)
                (setq pt (cdr (assoc 10 (entget (ssname ss1 0))))) 
                (setq ptlist (cons pt ptlist))
            ) ;repeat
            (repeat (length ptlist)
                (setq blk (entmake
                    (append
                        (list (cons 0 "INSERT") (cons 8 (cdr (assoc 8 selBlk))))
                        (subst (car ptlist) '(10) (entget selBlk))
                    )
                ))
                (setq ptlist (cdr ptlist))
            ) ;repeat
            (redraw)
            (setq ss2 (ssget "_X" (list (cons 0 "INSERT") (cons 8 (cdr (assoc 8 selBlk)))))) 
            (message "Inserted %d block(s)." (sslength ss2))
        ) ;progn
        (prompt "\nNo polyline or block reference selected.")
    ) ;if
) ;defun