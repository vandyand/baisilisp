;; Portable clojure.core.match/basilisp.core.match subset conformance.

#?(:clj
   (require '[clojure.core.match :refer [match match-let matchm matchv]])
   :lpy
   (require '[basilisp.core.match :refer [match match-let matchm matchv]]))

(def match-ns #?(:clj 'clojure.core.match
                 :lpy 'basilisp.core.match))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :portable-public-subset
           (into {}
                 (map (fn [sym]
                        [sym (contains? (ns-publics match-ns) sym)])
                      '[match match-let matchm matchv])))

(emit-case :scalar-and-vector-patterns
           [(match 1
              1 :one
              :else :other)
            (match [1 2 4]
              [1 2 b] [:first b]
              [a 2 4] [:second a]
              :else :bad)
            (match [[1 2 3 4]]
              [[1 2 & tail]] tail
              :else :bad)])

(emit-case :map-patterns
           [(match [{:a nil}]
              [{:a x}] [:present x]
              :else :bad)
            (match [{:a nil}]
              [{:b nil}] :bad
              :else :missing)
            (match [{:a 1 :b 2}]
              [{:a 1 :b x}] [:value x]
              :else :bad)])

(emit-case :seq-patterns
           [(match [nil]
              [([] :seq)] :empty
              :else :bad)
            (match ['(1 2 4)]
              [([1 2 b] :seq)] [:seq b]
              :else :bad)
            (match ['(1 2 3)]
              [([1 & r] :seq)] [r (first r)]
              :else :bad)
            (match ['(1 2 3)]
              [([1 & [2 x]] :seq)] x
              :else :bad)])

(emit-case :seq-pattern-scalar-fallback
           [(match [41]
              [([1 2] :seq)] :bad
              :else [:fallback 41])
            (match [:keyword]
              [([:a :b] :seq)] :bad
              :else [:fallback :keyword])])

(emit-case :application-and-as-patterns
           [(match [[1 2 3]]
              [[1 (3 :<< inc) 3]] :app
              :else :bad)
            (match [{:a 1 :b 2}]
              [{:a (2 :<< inc) :b _}] :app-map
              :else :bad)
            (match [[1 2]]
              [([a b] :as whole)] [a b whole]
              :else :bad)])

(emit-case :wrapper-macros
           [(matchm [{:a 1 :b 2}]
              [{:a 1 :b x}] x
              :else :bad)
            (match-let [x [1 2]]
              [[1 2]] :ok
              :else :bad)])
