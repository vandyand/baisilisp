;; Portable recursive clojure.spec.alpha generation behavior.
;;
;; Raw generated examples are intentionally not compared because Clojure and
;; Basilisp use different RNG implementations. These cases lock the observable
;; semantic contract: generation terminates, generated values conform, and
;; recursive branches appear within bounded samples.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as sgen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn depth [x]
  (if (vector? x)
    (inc (reduce max 0 (map depth x)))
    0))

(s/def :tests.spec-recursive/tree
       (s/or :leaf int?
             :node (s/coll-of :tests.spec-recursive/tree
                              :kind vector?
                              :max-count 3)))

(s/def :tests.spec-recursive/a
       (s/or :leaf int?
             :node :tests.spec-recursive/b))

(s/def :tests.spec-recursive/b
       (s/coll-of :tests.spec-recursive/a
                  :kind vector?
                  :max-count 2))

(emit-case :self-recursive-generation
           (let [samples (sgen/sample (s/gen :tests.spec-recursive/tree) 80)]
             {:count (count samples)
              :every-valid? (every? #(s/valid? :tests.spec-recursive/tree %)
                                    samples)
              :some-recursive-branch? (boolean (some vector? samples))
              :bounded-depth? (<= (reduce max 0 (map depth samples)) 12)}))

(emit-case :mutual-recursive-generation
           (let [samples (sgen/sample (s/gen :tests.spec-recursive/a) 80)]
             {:count (count samples)
              :every-valid? (every? #(s/valid? :tests.spec-recursive/a %)
                                    samples)
              :some-recursive-branch? (boolean (some vector? samples))
              :bounded-depth? (<= (reduce max 0 (map depth samples)) 12)}))
