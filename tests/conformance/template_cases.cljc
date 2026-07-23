;; Portable clojure.template/basilisp.template cases. The namespace is small,
;; but macro templating is used by test-style DSLs and needs exact replacement,
;; grouping, and macroexpansion behavior.

(require '[clojure.template :as template])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn generated-value [seed]
  (case (mod seed 7)
    0 seed
    1 (keyword (str "kw" seed))
    2 (symbol (str "sym" seed))
    3 (str "s" seed)
    4 [seed (inc seed)]
    5 {:seed seed}
    #{seed (inc seed)}))

(defn generated-template [seed]
  (case (mod seed 5)
    0 '(list x y)
    1 '[x {:inner y} #{x y}]
    2 '{:x x :y y x y}
    3 '(quote [x y])
    '(vector {:x x} (list y x))))

(defn generated-apply-case [seed]
  (let [x (generated-value (+ seed 1))
        y (generated-value (+ seed 2))]
    {:seed seed
     :value (template/apply-template '[x y]
                                     (generated-template seed)
                                     [x y])}))

(emit-case :public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.template
                                                :lpy 'basilisp.template))))))

(emit-case :apply-template-boundaries
           {:basic (template/apply-template '[x y] '(= x y) '[1 2])
            :duplicate-bindings (template/apply-template '[x x] '(list x) '[1 2])
            :short-values (template/apply-template '[x y] '(list x y) '[1])
            :long-values (template/apply-template '[x] '(list x) '[1 2])
            :map-key-and-value-replacement (template/apply-template '[x]
                                                                    '{:x x x :symbol}
                                                                    '[:value])
            :quoted-template (template/apply-template '[x] ''x '[:value])})

(emit-case :do-template-macroexpansion
           {:basic (macroexpand '(template/do-template [x y]
                                   (= x y)
                                   1 (inc 0)
                                   2 (dec 3)))
            :incomplete-group-dropped (macroexpand '(template/do-template [x y]
                                                      (= x y)
                                                      1 2 3))
            :nested-form (macroexpand '(template/do-template [x y z]
                                         {:left x :right [y z]}
                                         :a 1 2
                                         :b 3 4))})

(emit-case :generated-apply-corpus
           (mapv generated-apply-case (range 96)))

(emit-case :generated-do-template-corpus
           (mapv (fn [seed]
                   {:seed seed
                    :form (macroexpand `(template/do-template [x y]
                                          ~(generated-template seed)
                                          ~(generated-value (+ seed 1))
                                          ~(generated-value (+ seed 2))
                                          ~(generated-value (+ seed 3))
                                          ~(generated-value (+ seed 4))
                                          :trailing))})
                 (range 48)))
