;; Exercise the source-level algo.generic port through deterministic public
;; contracts under both Clojure and Basilisp.

(doseq [source ["generic"
                "generic/arithmetic"
                "generic/collection"
                "generic/comparison"
                "generic/functor"
                "generic/math_functions"]]
  (load-file (str "tests/acceptance/upstream/algo-generic/port/src/basilisp/algo/"
                  source
                  ".cljc")))

(alias 'ga 'basilisp.algo.generic.arithmetic)
(alias 'gc 'basilisp.algo.generic.comparison)
(alias 'gcoll 'basilisp.algo.generic.collection)
(alias 'gf 'basilisp.algo.generic.functor)
(alias 'gm 'basilisp.algo.generic.math-functions)

(defrecord box [value])

(defmethod gc/zero? box [x] (zero? (:value x)))
(defmethod gc/= [box box] [x y] (= (:value x) (:value y)))
(defmethod gc/> [box box] [x y] (> (:value x) (:value y)))
(defmethod ga/+ [box box] [x y] (->box (+ (:value x) (:value y))))
(defmethod ga/- box [x] (->box (- (:value x))))
(defmethod ga/* [box box] [x y] (->box (* (:value x) (:value y))))
(ga/defmethod* basilisp.algo.generic.arithmetic / box [x]
  (->box (/ (:value x))))
(defmethod gm/conjugate box [x] (->box (- (:value x))))
(defmethod gm/abs box [x] (->box (if (neg? (:value x)) (- (:value x)) (:value x))))

(defrecord bag [items])
(defmethod gcoll/conj bag [b & xs] (->bag (into (:items b) xs)))
(defmethod gcoll/empty bag [_] (->bag []))
(defmethod gcoll/seq bag [b] (seq (:items b)))
(defmethod gf/fmap bag [f b] (->bag (mapv f (:items b))))

(let [mapped-future (gf/fmap inc (future 10))
      mapped-delay  (gf/fmap inc (delay 20))
      composed      (gf/fmap inc (fn [x] (* x 2)))]
  (println
   (pr-str
    {:comparison [(gc/zero? 0)
                  (gc/pos? 3)
                  (gc/neg? -1)
                  (gc/= 1 1 1)
                  (gc/not= 1 2)
                  (gc/< 1 2 3)
                  (gc/> 3 2 1)
                  (gc/>= 3 3 1)
                  (gc/<= 1 1 2)
                  (gc/max 1 5 3)
                  (gc/min 1 5 3)]
     :arithmetic [(ga/+ 1 2 3)
                  (ga/- 10 2 3)
                  (ga/* 2 3 4)
                  (ga// 24 2 3)]
     :custom [(mapv :value [(ga/+ (->box 2) (->box 5))
                            (ga/- (->box 9))
                            (ga/* (->box 3) (->box 4))
                            (ga// (->box 2))])
              (gc/> (->box 3) (->box 2))
              (mapv :value [(gm/conjugate (->box 8))
                            (gm/abs (->box -8))])]
     :collection [(gcoll/assoc {:a 1} :b 2)
                  (gcoll/conj [1] 2 3)
                  (gcoll/dissoc {:a 1 :b 2} :a)
                  (gcoll/empty [1 2])
                  (gcoll/get {:a 1} :missing :fallback)
                  (:items (gcoll/into (->bag []) [1 2 3]))
                  (vec (gcoll/seq (->bag [1 2 3])))]
     :functor [(gf/fmap inc [1 2 3])
               (gf/fmap inc '(1 2 3))
               (gf/fmap inc {:a 1 :b 2})
               (gf/fmap inc #{1 2 3})
               (composed 4)
               @mapped-future
               @mapped-delay
               (gf/fmap inc nil)
               (:items (gf/fmap inc (->bag [1 2 3])))]
     :math [(gm/sqrt 9)
            (gm/pow 2 4)
            (gm/sin 0)
            (gm/cos 0)
            (gm/abs -5)
            (gm/round 2.6)
            (gm/sgn -3)
            (:value (gm/sqr (->box 7)))
            (gm/approx= 1.0 1.0001 0.01)]})))
