(defun c:CleanDynRotate ( / ss i ent blkObj props prop propName curDynValue newBlkRot acadObj doc cmde oldRegen)
  (vl-load-com)
  
  (setq acadObj (vlax-get-acad-object)
        doc     (vla-get-ActiveDocument acadObj)
  )
  
  (princ "\nВыберите блоки для быстрой обработки (10000+):")
  (setq ss (ssget '((0 . "INSERT"))))
  
  (if ss
    (progn
      ;; Сохраняем старые настройки и отключаем эхо команд
      (setq cmde (getvar "CMDECHO"))
      (setvar "CMDECHO" 0)
      
      ;; Отключаем автоматическую регенерацию экрана чертежа
      (setq oldRegen (getvar "REGENMODE"))
      (setvar "REGENMODE" 0)
      
      (vla-StartUndoMark doc)
      
      (setq i (sslength ss))
      (while (> i 0)
        (setq i (1- i))
        (setq ent (ssname ss i))
        (setq blkObj (vlax-ename->vla-object ent))
        
        ;; Быстрая проверка на динамический блок
        (if (= (vlax-get-property blkObj 'IsDynamicBlock) :vlax-true)
          (progn
            ;; Получаем массив свойств и преобразуем его в список lisp за один шаг
            (setq props (vlax-safearray->list (vlax-variant-value (vla-GetDynamicBlockProperties blkObj))))
            
            ;; Используем быстрый foreach вместо вложенного цикла
            (foreach prop props
              (setq propName (vlax-get-property prop 'PropertyName))
              
              (if (member propName '("Угол" "Угол1" "Angle" "Angle1"))
                (progn
                  ;; Читаем значение динамического параметра
                  (setq curDynValue (vlax-variant-value (vlax-get-property prop 'Value)))
                  
                  ;; Вычисляем новый поворот самого блока
                  (setq newBlkRot (- curDynValue 1.5707963267948966))
                  
                  ;; Записываем свойства напрямую без лишних проверок
                  (vlax-put-property blkObj 'Rotation newBlkRot)
                  (vlax-put-property prop 'Value 1.5707963267948966) ;; 90 градусов в радианах
                )
              )
            )
          )
        )
      )
      
      (vla-EndUndoMark doc)
      
      ;; Возвращаем настройки регенерации назад
      (setvar "REGENMODE" oldRegen)
      (setvar "CMDECHO" cmde)
      
      ;; Принудительно обновляем экран всего ОДИН раз для всех 10 000 блоков
      (vla-Regen doc acAllViewports)
      
      (princ (strcat "\nУспешно и быстро обработано блоков: " (itoa (sslength ss))))
    )
  )
  (princ)
)

(princ "\nИсправленный скоростной лисп загружен. Команда: CleanDynRotateFast")
(princ)
