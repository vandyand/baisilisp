;; Legacy clojure.parallel source audit plus Basilisp compatibility semantics.
;;
;; JVM Clojure 1.12.4 ships clojure/parallel.clj, but requiring the namespace
;; fails on the verified baseline because it imports obsolete jsr166y classes.
;; These cases therefore audit the bundled Clojure source on :clj and execute
;; Basilisp's sequential compatibility layer on :lpy.

(ns conformance.parallel-cases
  (:require
   [clojure.string :as str]
   #?(:clj [clojure.java.io :as io])
   #?(:lpy [clojure.parallel :as parallel])))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def expected-publics
  ["pany"
   "par"
   "pdistinct"
   "pfilter-dupes"
   "pfilter-nils"
   "pmax"
   "pmin"
   "preduce"
   "psort"
   "psummary"
   "pvec"])

(def expected-arglists
  '{par ([coll] [coll & ops])
    pany ([coll])
    pmax ([coll] [coll comp])
    pmin ([coll] [coll comp])
    psummary ([coll] [coll comp])
    preduce ([f base coll])
    pvec ([pa])
    pdistinct ([coll])
    psort ([coll] [coll comp])
    pfilter-nils ([coll])
    pfilter-dupes ([coll])})

#?(:clj
   (def legacy-source
     (slurp (io/resource "clojure/parallel.clj"))))

#?(:clj
   (defn source-publics []
     (sort (map second (re-seq #"(?m)^\(defn\s+([^\s\[]+)" legacy-source)))))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

#?(:lpy
   (defn sample-vector [seed]
     (vec (map (fn [idx]
                 (- (mod (+ (* seed 31) (* idx 17)) 37) 18))
               (range (mod seed 48))))))

#?(:lpy
   (defn throws? [f]
     (try
       (f)
       false
       (catch Exception _ true))))

#?(:lpy
   (defn expected-pipeline
     [xs ys start end offset]
     (->> xs
          (map-indexed vector)
          (drop start)
          (take (- end start))
          (filter (fn [[_idx value]] (even? value)))
          (filter (fn [[idx _value]] (not= 0 (mod idx 3))))
          (filter (fn [[idx value]] (< value (nth ys idx))))
          (map (fn [[idx value]] [idx (* value idx)]))
          (map (fn [[idx value]] [idx (+ value offset)]))
          (map (fn [[idx value]] (+ value (nth ys idx))))
          vec)))

(emit-case :legacy-public-source-surface
           #?(:clj (= expected-publics (source-publics))
              :lpy (and (every? #(contains? (ns-publics 'clojure.parallel)
                                            (symbol %))
                                expected-publics)
                        (= (find-ns 'basilisp.parallel)
                           (find-ns 'clojure.parallel)))))

(emit-case :legacy-arglists-and-alias-boundary
           #?(:clj (every? (fn [[sym arglists]]
                             (and (str/includes? legacy-source
                                                 (str "(defn " (name sym)))
                                  (every? #(str/includes? legacy-source
                                                          (pr-str %))
                                          arglists)))
                           expected-arglists)
              :lpy (and (= (find-ns 'basilisp.parallel)
                           (find-ns 'clojure.parallel))
                        (every? (fn [[sym arglists]]
                                  (= arglists
                                     (:arglists
                                      (meta (ns-resolve 'clojure.parallel
                                                        sym)))))
                                expected-arglists))))

(emit-case :odd-trailing-op-source-boundary
           #?(:clj (str/includes? legacy-source "(partition 2 ops)")
              :lpy (= [1 2 3]
                      (parallel/pvec (parallel/par [1 2 3] :map)))))

(emit-case :legacy-operation-keywords
           #?(:clj (every? #(str/includes? legacy-source %)
                           [":bound"
                            ":filter"
                            ":filter-index"
                            ":filter-with"
                            ":map"
                            ":map-index"
                            ":map-with"])
              :lpy (= [0 4 16]
                      (parallel/pvec
                       (parallel/par (range 5)
                                     :bound [0 5]
                                     :filter even?
                                     :map-index *)))))

(emit-case :aggregate-compatibility-boundaries
           #?(:clj (every? #(str/includes? legacy-source %)
                           ["defn pany"
                            "defn pmax"
                            "defn pmin"
                            "defn psummary"
                            "defn preduce"])
              :lpy (let [plan (parallel/par [3 nil 1 2 2 1 nil]
                                            :filter some?
                                            :map identity)]
                     (= {:any 3
                         :max 3
                         :min 1
                         :summary {:min 1
                                   :max 3
                                   :size 5
                                   :min-index 1
                                   :max-index 0}
                         :sum 9}
                        {:any (parallel/pany plan)
                         :max (parallel/pmax plan)
                         :min (parallel/pmin plan)
                         :summary (parallel/psummary plan)
                         :sum (parallel/preduce + 0 plan)}))))

(emit-case :collection-producing-boundaries
           #?(:clj (every? #(str/includes? legacy-source %)
                           ["defn pvec"
                            "defn pdistinct"
                            "defn psort"
                            "defn pfilter-nils"
                            "defn pfilter-dupes"])
              :lpy (let [plan (parallel/par [3 nil 1 2 2 1 nil]
                                            :filter some?)]
                     (= {:vec [3 1 2 2 1]
                         :distinct [3 1 2]
                         :sort [1 1 2 2 3]
                         :nils [3 1 2 2 1]
                         :dupes [3 1 2 1]}
                        {:vec (parallel/pvec plan)
                         :distinct (parallel/pdistinct plan)
                         :sort (parallel/psort plan)
                         :nils (parallel/pfilter-nils [3 nil 1 2 2 1 nil])
                         :dupes (parallel/pfilter-dupes plan)}))))

(emit-case :seeded-map-filter-reduce-corpus
           #?(:clj (and (str/includes? legacy-source "withMapping")
                        (str/includes? legacy-source "withFilter")
                        (str/includes? legacy-source "reduce (reducer f) base"))
              :lpy (loop [remaining 96
                          seed 195936478
                          ok? true]
                     (if (or (zero? remaining) (not ok?))
                       ok?
                       (let [s1 (next-seed seed)
                             s2 (next-seed s1)
                             xs (sample-vector s1)
                             offset (- (mod s2 11) 5)
                             expected (vec (map #(+ % offset)
                                                (filter even? xs)))
                             plan (parallel/par xs
                                                :filter even?
                                                :map #(+ % offset))]
                         (recur (dec remaining)
                                s2
                                (and (= expected (parallel/pvec plan))
                                     (= (reduce + 0 expected)
                                        (parallel/preduce + 0 plan))
                                     (= (vec (distinct expected))
                                        (parallel/pdistinct plan)))))))))

(emit-case :seeded-indexed-and-with-corpus
           #?(:clj (and (str/includes? legacy-source "withIndexedFilter")
                        (str/includes? legacy-source "withIndexedMapping")
                        (str/includes? legacy-source "withMapping (binary-op")
                        (str/includes? legacy-source "withFilter (binary-predicate"))
              :lpy (loop [remaining 96
                          seed 610839776
                          ok? true]
                     (if (or (zero? remaining) (not ok?))
                       ok?
                       (let [s1 (next-seed seed)
                             s2 (next-seed s1)
                             xs (sample-vector s1)
                             ys (vec (map #(+ % 1000) (range (count xs))))
                             expected-indexed (vec
                                               (keep-indexed
                                                (fn [idx value]
                                                  (when (even? idx)
                                                    (* value idx)))
                                                xs))
                             expected-with (vec
                                            (map (fn [[x y]] (+ x y))
                                                 (filter (fn [[x y]] (> y x))
                                                         (map vector xs ys))))
                             indexed-plan (parallel/par xs
                                                        :filter-index
                                                        (fn [_value idx] (even? idx))
                                                        :map-index *)
                             with-plan (parallel/par xs
                                                     :filter-with
                                                     [(fn [x y] (> y x)) ys]
                                                     :map-with
                                                     [+ ys])]
                         (recur (dec remaining)
                                s2
                                (and (= expected-indexed
                                        (parallel/pvec indexed-plan))
                                     (= expected-with
                                        (parallel/pvec with-plan)))))))))

(emit-case :bound-index-and-with-composition-corpus
           #?(:clj (and (str/includes? legacy-source "withBounds")
                        (str/includes? legacy-source "withIndexedFilter")
                        (str/includes? legacy-source "withIndexedMapping")
                        (str/includes? legacy-source "withMapping (binary-op"))
              :lpy (loop [remaining 192
                          seed 3735928559
                          ok? true]
                     (if (or (zero? remaining) (not ok?))
                       ok?
                       (let [s1 (next-seed seed)
                             s2 (next-seed s1)
                             xs (sample-vector s1)
                             ys (vec (map #(+ 50 %) (range (count xs))))
                             n (count xs)
                             start (if (zero? n) 0 (mod s2 n))
                             width (if (zero? n)
                                     0
                                     (mod (quot s2 17) (inc (- n start))))
                             end (+ start width)
                             offset (- (mod s2 9) 4)
                             expected (expected-pipeline xs ys start end offset)
                             plan (parallel/par xs
                                                :bound [start end]
                                                :filter even?
                                                :filter-index
                                                (fn [_value idx]
                                                  (not= 0 (mod idx 3)))
                                                :filter-with
                                                [(fn [x y] (< x y)) ys]
                                                :map-index *
                                                :map #(+ % offset)
                                                :map-with [+ ys])]
                         (recur (dec remaining)
                                s2
                                (= expected (parallel/pvec plan))))))))

(emit-case :adversarial-empty-and-error-boundaries
           #?(:clj (and (str/includes? legacy-source
                                       "Unsupported par op")
                        (str/includes? legacy-source
                                       "(partition 2 ops)")
                        (str/includes? legacy-source
                                       "removeConsecutiveDuplicates"))
              :lpy (= {:empty-vec []
                       :nil-vec []
                       :empty-any nil
                       :nil-filter []
                       :dupes [nil 1 nil 2]
                       :odd-trailing [1 2 3]
                       :bad-op true
                       :short-other true}
                      {:empty-vec (parallel/pvec [])
                       :nil-vec (parallel/pvec nil)
                       :empty-any (parallel/pany [])
                       :nil-filter (parallel/pfilter-nils nil)
                       :dupes (parallel/pfilter-dupes
                               [nil nil 1 1 nil nil 2])
                       :odd-trailing (parallel/pvec
                                      (parallel/par [1 2 3] :map))
                       :bad-op (throws? #(parallel/par [1 2 3]
                                                       :explode identity))
                       :short-other (throws?
                                     #(parallel/pvec
                                       (parallel/par [1 2 3]
                                                     :map-with [+ [10]])))})))

(emit-case :aggregate-comparator-boundaries
           #?(:clj (and (str/includes? legacy-source "summary comp")
                        (str/includes? legacy-source "sort comp")
                        (str/includes? legacy-source "max comp")
                        (str/includes? legacy-source "min comp"))
              :lpy (let [xs [3 -10 2 -4]
                         abs-comp (fn [a b] (compare (abs a) (abs b)))]
                     (= {:sort [2 3 -4 -10]
                         :min 2
                         :max -10
                         :summary {:min 2
                                   :max -10
                                   :size 4
                                   :min-index 2
                                   :max-index 1}}
                        {:sort (parallel/psort xs abs-comp)
                         :min (parallel/pmin xs abs-comp)
                         :max (parallel/pmax xs abs-comp)
                         :summary (parallel/psummary xs abs-comp)}))))
