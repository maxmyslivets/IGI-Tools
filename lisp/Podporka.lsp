(defun c:PODPORKA ( / acadObj doc modelSpc sel1 ent1 obj1 sel2 ent2 obj2 len dist pt param deriv dx dy ang pClose distVal blk prop pName targetAng)
  (vl-load-com)
  (setq acadObj (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadObj))
  (setq modelSpc (vla-get-ModelSpace doc))
  
  (setq sel1 (entsel "\nВыберите первую полилинию (ось): "))
  (if (not sel1) (exit))
  (setq ent1 (car sel1))
  (setq obj1 (vlax-ename->vla-object ent1))
  
  (setq sel2 (entsel "\nВыберите вторую полилинию (цель): "))
  (if (not sel2) (exit))
  (setq ent2 (car sel2))
  (setq obj2 (vlax-ename->vla-object ent2))
  
  (setq len (vlax-curve-getDistAtParam obj1 (vlax-curve-getEndParam obj1)))
  (setq dist 0.0)
  
  (while (<= dist len)
    (setq pt (vlax-curve-getPointAtDist obj1 dist))
    
    ;; 1. Получаем проекцию на вторую линию ТОЛЬКО для определения правильной полуплоскости (стороны)
    (setq pClose (vlax-curve-getClosestPointTo obj2 pt))
    
    ;; 2. Находим параметры касательной к первой линии (оси) в текущей точке
    (setq param (vlax-curve-getParamAtDist obj1 dist))
    (setq deriv (vlax-curve-getFirstDeriv obj1 param))
    
    ;; Вычисляем угол касательной и базовый перпендикуляр (+90 градусов)
    (setq tangAng (atan (cadr deriv) (car deriv)))
    (setq ang (+ tangAng (/ pi 2.0)))
    
    ;; Направление на вторую линию для выбора правильной стороны перпендикуляра
    (setq tgtAng (atan (- (cadr pClose) (cadr pt)) (- (car pClose) (car pt))))
    (if (< (cos (- ang tgtAng)) 0.0)
      (setq ang (- ang pi))
    )
    
    ;; 3. ВЫЧИСЛЕНИЕ ТОЧНОЙ ДЛИНЫ ДО ПЕРЕСЕЧЕНИЯ
    ;; Строим временный виртуальный луч в пространстве модели из точки вставки в направлении перпендикуляра
    (setq tmpRay (vla-AddRay modelSpc (vlax-3d-point pt) (vlax-3d-point (polar pt ang 1.0))))
    
    ;; Ищем пересечение луча со второй полилинией (без продления линии obj2)
    (setq intPt (vlax-invoke tmpRay 'IntersectWith obj2 acExtendNone))
    
    ;; Проверяем, пересеклись ли они
    (if intPt
      ;; Если пересечение найдено, рассчитываем расстояние до этой точной точки
      (setq distVal (distance pt (list (car intPt) (cadr intPt) (caddr intPt))))
      ;; Запасной вариант (если луч прошел мимо из-за сложной геометрии): берем кратчайшее расстояние
      (setq distVal (distance pt pClose))
    )
    
    ;; Удаляем временный луч из чертежа, чтобы не засорять память
    (vla-delete tmpRay)
    
    ;; 4. Вставляем блок с углом, строго перпендикулярным оси
    (setq blk (vla-InsertBlock modelSpc (vlax-3d-point pt) "СП_3.59.2" 1.0 1.0 1.0 ang))
    
    ;; Настраиваем динамические свойства блока
    (if (= (vla-get-IsDynamicBlock blk) :vlax-true)
      (foreach prop (vlax-invoke blk 'GetDynamicBlockProperties)
        (setq pName (vla-get-PropertyName prop))
        (cond
          ;; Растягиваем блок ровно до точки физического пересечения перпендикуляра с целью
          ((= pName "Расстояние1") (vla-put-Value prop distVal))
          ;; Обнуляем внутреннее свойство поворота
          ((= pName "Угол1") (vla-put-Value prop 0.0))
        )
      )
    )
    
    (setq dist (+ dist 2.0))
  )

  (princ "\nГотово! Все блоки развернуты к целевой линии.")
  (princ)
)
