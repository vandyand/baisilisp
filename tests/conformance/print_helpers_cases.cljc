;; ``print-ctor`` uses host type names, so compare its portable framing and
;; callback behavior rather than concrete Java/Python class spellings.

(ns conformance.print-helpers-cases
  (:require [clojure.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [value      (with-meta [1] {:tag 'kind})
      plain      (with-out-str (print-simple value *out*))
      metadata   (binding [*print-meta* true
                           *print-readably* true]
                   (with-out-str (print-simple value *out*)))
      duplicate  (binding [*print-dup* true]
                   (with-out-str (print-simple value *out*)))
      ctor-value (with-out-str
                   (print-ctor 1 (fn [object writer]
                                   (.write writer (str "args-" object)))
                               *out*))]
  (emit-case :print-helpers
             {:plain? (= "[1]" plain)
              :metadata? (= "^kind ^kind [1]" metadata)
              :duplicate-metadata? (= "^kind ^kind [1]" duplicate)
              :ctor-framed? (and (str/starts-with? ctor-value "#=(")
                                 (str/ends-with? ctor-value ". args-1)"))}))

(defn stable-map-print
  [m]
  (binding [*print-namespace-maps* false]
    (pr-str (into (sorted-map) m))))

(def sample-escaped-string
  (str "a" \newline "b" \tab (char 92) "c"))

(emit-case :adversarial-print-metadata-readability
           (let [v (with-meta [1] {:tag 'kind})
                 m (with-meta (sorted-map :a 1) {:tag 'kind})
                 map-dup (binding [*print-meta* false
                                   *print-readably* false
                                   *print-dup* true]
                           (pr-str m))]
             {:vector-meta-readable (binding [*print-meta* true
                                              *print-readably* true]
                                     (pr-str v))
              :vector-meta-unreadable (binding [*print-meta* true
                                                *print-readably* false]
                                       (pr-str v))
              :vector-meta-dup (binding [*print-meta* false
                                         *print-readably* false
                                         *print-dup* true]
                                (pr-str v))
              :map-meta-readable (binding [*print-meta* true
                                           *print-readably* true]
                                  (pr-str m))
              :map-meta-unreadable (binding [*print-meta* true
                                             *print-readably* false]
                                    (pr-str m))
              :map-meta-dup {:tag-prefix? (str/starts-with? map-dup "^kind ")
                             :contains-entry? (str/includes? map-dup ":a 1")}}))

(emit-case :adversarial-print-truncation-and-namespace-maps
           {:print-length-zero (binding [*print-length* 0]
                                (pr-str [1 2]))
            :print-length-one-vector (binding [*print-length* 1]
                                      (pr-str [1 2 3]))
            :print-length-one-map (binding [*print-length* 1]
                                   (pr-str (sorted-map :a 1 :b 2)))
            :print-level-zero (binding [*print-level* 0]
                                (pr-str [1 [2]]))
            :print-level-one-map (binding [*print-level* 1]
                                  (pr-str (sorted-map :a [1] :b (sorted-map :c 2))))
            :namespace-map (binding [*print-namespace-maps* true]
                             (pr-str (sorted-map :a/x 1 :a/y 2)))
            :mixed-namespace-map (binding [*print-namespace-maps* true]
                                  (pr-str (sorted-map :a/x 1 :b/y 2)))
            :unreadable-string (binding [*print-readably* false]
                                 (pr-str "a\nb"))})

(emit-case :adversarial-print-source-resource-boundaries
           (let [tagged (tagged-literal 'foo/bar [1 2])
                 tagged-map (tagged-literal 'foo/bar {:a [1]})]
             {:chars [(pr-str \a)
                      (pr-str \space)
                      (print-str \space)
                      (binding [*print-readably* false]
                        (pr-str \newline))]
              :strings [(pr-str sample-escaped-string)
                        (binding [*print-readably* false]
                          (pr-str sample-escaped-string))]
              :namespace-map-default [(= true *print-namespace-maps*)
                                      (pr-str (sorted-map :a/x 1
                                                          :a/y 2))]
              :tagged [(pr-str tagged)
                       (binding [*print-length* 1]
                         (pr-str tagged))
                       (binding [*print-level* 1]
                         (pr-str tagged-map))]
              :namespace-map-limits [(binding [*print-namespace-maps* true
                                               *print-length* 1]
                                      (pr-str (sorted-map :a/x 1 :a/y 2)))
                                    (binding [*print-namespace-maps* true
                                              *print-level* 1]
                                      (pr-str (sorted-map :a/x [1]
                                                          :a/y {:z 2})))
                                    (binding [*print-namespace-maps* true
                                              *print-meta* true]
                                      (pr-str
                                       (with-meta
                                         (sorted-map :a/x 1 :a/y 2)
                                         {:a/m 1})))]
              :sets [(binding [*print-length* 2]
                       (pr-str (sorted-set 1 2 3)))
                     (binding [*print-level* 0]
                       (pr-str (sorted-set 1 2 3)))]}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn printable-value [seed depth]
  (let [choice (mod seed 12)]
    (cond
      (zero? depth) (case (mod seed 5)
                      0 seed
                      1 (keyword "k" (str "v" (mod seed 7)))
                      2 (symbol "s" (str "v" (mod seed 7)))
                      3 (str "s" (mod seed 11))
                      nil)
      (= choice 0) [(printable-value (next-seed seed) (dec depth))
                    (printable-value (next-seed (next-seed seed)) (dec depth))]
      (= choice 1) (list (printable-value (next-seed seed) (dec depth))
                         (printable-value (next-seed (next-seed seed)) (dec depth)))
      (= choice 2) (sorted-set (mod seed 17)
                               (mod (next-seed seed) 17)
                               (mod (next-seed (next-seed seed)) 17))
      (= choice 3) (sorted-map :a (printable-value (next-seed seed) (dec depth))
                               :b (printable-value (next-seed (next-seed seed))
                                                   (dec depth)))
      (= choice 4) (with-meta [(mod seed 9)] {:tag 'generated})
      (= choice 5) (str "text-" (mod seed 13))
      (= choice 6) (keyword "generated" (str "k" (mod seed 19)))
      (= choice 7) (symbol "generated" (str "s" (mod seed 23)))
      (= choice 8) (case (mod seed 4)
                     0 \a
                     1 \space
                     2 \newline
                     \tab)
      (= choice 9) (tagged-literal 'generated/value
                                   [(mod seed 7)
                                    (printable-value (next-seed seed)
                                                     (dec depth))])
      (= choice 10) (sorted-map :a/x (printable-value (next-seed seed)
                                                      (dec depth))
                                :a/y (printable-value
                                      (next-seed (next-seed seed))
                                      (dec depth)))
      :else (symbol "generated" (str "s" (mod seed 23))))))

(emit-case :seeded-printable-corpus
           (mapv (fn [seed]
                   (let [value (printable-value seed 3)]
                     {:seed seed
                      :plain (pr-str value)
                      :limited (binding [*print-length* 2
                                         *print-level* 2]
                                 (pr-str value))
                      :unreadable-meta (binding [*print-meta* true
                                                 *print-readably* false]
                                         (pr-str value))}))
                 (take 36 (iterate next-seed 20260725))))
