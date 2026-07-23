;; Portable clojure.test.check/basilisp.test.check behavior.
;;
;; Exact generated values are intentionally not compared: Basilisp uses a
;; Python-hosted deterministic RNG rather than Java's test.check RNG. This
;; fixture locks public contract shape, generator invariants, property result
;; maps, shrinking behavior, and result-data namespace keys.

(ns tests.conformance.test-check-cases
  #?(:clj
     (:require [clojure.test.check :as tc]
               [clojure.test.check.clojure-test :as ct]
               [clojure.test.check.generators :as gen]
               [clojure.test.check.properties :as prop]
               [clojure.test.check.random :as rnd]
               [clojure.test.check.results :as results]
               [clojure.test.check.rose-tree :as rose])
     :lpy
     (:require [basilisp.test.check :as tc]
               [basilisp.test.check.clojure-test :as ct]
               [basilisp.test.check.generators :as gen]
               [basilisp.test.check.properties :as prop]
               [basilisp.test.check.random :as rnd]
               [basilisp.test.check.results :as results]
               [basilisp.test.check.rose-tree :as rose])))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def portable-generator-names
  '[->Generator any any-equatable any-printable
    any-printable-equatable big-ratio bind boolean byte bytes call-gen char
    char-alpha char-alpha-numeric char-alphanumeric char-ascii choose container-type
    double double* elements fmap frequency gen-bind gen-fmap gen-pure generate
    generator? hash-map int keyword keyword-ns large-integer large-integer*
    lazy-random-states let list list-distinct list-distinct-by
    make-size-range-seq map
    map->Generator nat neg-int no-shrink not-empty one-of pos-int ratio
    recursive-gen resize return s-neg-int s-pos-int sample sample-seq scale set
    shrink-2 shuffle simple-type simple-type-equatable simple-type-printable
    simple-type-printable-equatable size-bounded-bigint sized small-integer
    sorted-set string string-alpha-numeric string-alphanumeric string-ascii
    such-that symbol symbol-ns tuple uuid vector vector-distinct
    vector-distinct-by])

(defn has-publics? [ns-sym names]
  (let [publics (ns-publics ns-sym)]
    (every? #(contains? publics %) names)))

(defn sample-ok? [pred generator n]
  (every? pred (gen/sample generator n)))

(def ascii-printable-strings
  (set (map str " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~")))

(defn result-summary [result]
  {:pass? (:pass? result)
   :num-tests (:num-tests result)
   :has-seed (contains? result :seed)
   :has-time (or (contains? result :time-elapsed-ms)
                 (contains? result :failed-after-ms))
   :fail-count (count (:fail result))
   :has-shrunk (contains? result :shrunk)
   :smallest-count (count (get-in result [:shrunk :smallest]))
   :shrunk-has-result (contains? (:shrunk result) :result)
   :shrunk-has-result-data (contains? (:shrunk result) :result-data)})

(emit-case :public-surface
           {:root (has-publics? #?(:clj 'clojure.test.check
                                   :lpy 'basilisp.test.check)
                                '[quick-check])
            :generators (has-publics? #?(:clj 'clojure.test.check.generators
                                         :lpy 'basilisp.test.check.generators)
                                      portable-generator-names)
            :properties (has-publics? #?(:clj 'clojure.test.check.properties
                                         :lpy 'basilisp.test.check.properties)
                                      '[->ErrorResult for-all for-all*
                                        map->ErrorResult])
            :results (has-publics? #?(:clj 'clojure.test.check.results
                                      :lpy 'basilisp.test.check.results)
                                   '[pass? result-data])
            :rose-tree (has-publics? #?(:clj 'clojure.test.check.rose-tree
                                        :lpy 'basilisp.test.check.rose-tree)
                                     '[->RoseTree bind children collapse filter
                                       fmap join make-rose permutations pure
                                       remove root seq shrink shrink-vector zip])
            :clojure-test (has-publics? #?(:clj 'clojure.test.check.clojure-test
                                           :lpy 'basilisp.test.check.clojure-test)
                                        '[*default-opts* *default-test-count*
                                          *report-completion* *report-shrinking*
                                          *report-trials* *trial-report-period*
                                          assert-check default-reporter-fn
                                          defspec process-options trial-report-dots
                                          trial-report-periodic with-test-out*])})

(emit-case :primitive-generator-invariants
           {:byte (sample-ok? #(<= -128 % 127) gen/byte 80)
            :small-integer (sample-ok? integer? gen/small-integer 80)
            :size-bounded (sample-ok? integer? gen/size-bounded-bigint 80)
            :big-ratio (sample-ok? number? gen/big-ratio 80)
            :ratio (sample-ok? number? gen/ratio 80)
            :char-ascii (sample-ok? #(contains? ascii-printable-strings (str %))
                                    gen/char-ascii
                                    80)
            :string-ascii (sample-ok? #(every? (fn [ch]
                                                 (contains? ascii-printable-strings
                                                            (str ch)))
                                               %)
                                      gen/string-ascii
                                      80)
            :keyword (sample-ok? keyword? gen/keyword 50)
            :symbol (sample-ok? symbol? gen/symbol 50)
            :uuid (sample-ok? uuid? gen/uuid 20)})

(emit-case :collection-generator-invariants
           {:vector-fixed (let [xs (gen/sample (gen/vector (gen/choose 0 9) 3) 50)]
                            (every? #(= 3 (count %)) xs))
            :vector-range (let [xs (gen/sample (gen/vector (gen/choose 0 9) 2 5) 50)]
                            (every? #(<= 2 (count %) 5) xs))
            :vector-distinct (let [xs (gen/sample
                                       (gen/vector-distinct
                                        (gen/choose 0 100)
                                        {:min-elements 3 :max-elements 8})
                                       50)]
                               (every? #(and (<= 3 (count %) 8)
                                             (= (count %) (count (set %))))
                                       xs))
            :map (let [xs (gen/sample (gen/map gen/keyword gen/small-integer
                                               {:max-elements 5})
                                      50)]
                   (every? map? xs))
            :set (let [xs (gen/sample (gen/set gen/small-integer
                                               {:max-elements 5})
                                      50)]
                   (every? set? xs))})

(emit-case :combinator-invariants
           {:return (gen/generate (gen/return :ok) 10 1)
            :fmap (sample-ok? even? (gen/fmap #(* 2 %) (gen/choose 0 20)) 50)
            :bind (let [g (gen/bind (gen/choose 1 5)
                                    (fn [n]
                                      (gen/fmap (fn [xs] [n xs])
                                                (gen/vector gen/nat n))))]
                    (sample-ok? #(= (first %) (count (second %))) g 50))
            :gen-let (let [g (gen/let [n (gen/choose 1 5)
                                       xs (gen/vector gen/nat n)]
                            [n xs])]
                       (sample-ok? #(= (first %) (count (second %))) g 50))
            :such-that (sample-ok? pos?
                                   (gen/such-that pos?
                                                  (gen/choose -20 20)
                                                  {:max-tries 100})
                                   50)})

(emit-case :constructors-and-rose-tree
           (let [g (gen/->Generator (fn [_ size] (rose/pure [:size size])))
                 gm (gen/map->Generator {:gen (fn [_ size]
                                                (rose/pure [:map-size size]))})
                 e1 (prop/->ErrorResult :boom)
                 e2 (prop/map->ErrorResult {:error :boom})
                 tree (rose/->RoseTree :root [(rose/pure :child)])
                 mapped (rose/fmap name (rose/pure :value))]
             {:generator? (gen/generator? g)
              :generated (gen/generate g 7 1)
              :map-generated (gen/generate gm 8 1)
              :error-result-pass? [(results/pass? e1) (results/pass? e2)]
              :error-result-data-keys [(contains? (results/result-data e1)
                                                  :clojure.test.check.properties/error)
                                       (contains? (results/result-data e1)
                                                  :basilisp.test.check.properties/error)]
              :rose-root (rose/root tree)
              :rose-child-count (count (rose/children tree))
              :rose-fmap-root (rose/root mapped)}))

(emit-case :auxiliary-rose-tree-helpers
           (let [t1 (rose/make-rose 1 [(rose/pure 10) (rose/pure 11)])
                 t2 (rose/make-rose 2 [(rose/pure 20)])
                 t3 (rose/make-rose 3 [])
                 roses [t1 t2 t3]
                 tree (rose/make-rose :root
                                      [(rose/make-rose :a [(rose/pure :aa)])
                                       (rose/pure :b)])
                 collapsed (rose/collapse tree)
                 zipped (rose/zip vector roses)
                 shrunk (rose/shrink vector roses)
                 shrinkv (rose/shrink-vector vector roses)]
             {:seq-values (vec (rose/seq tree))
              :collapse-root (rose/root collapsed)
              :collapse-child-roots (mapv rose/root (rose/children collapsed))
              :permutation-roots (mapv #(mapv rose/root %) (rose/permutations roses))
              :remove-roots (mapv #(mapv rose/root %) (rose/remove roses))
              :zip-root (rose/root zipped)
              :zip-child-roots (mapv rose/root (rose/children zipped))
              :shrink-root (rose/root shrunk)
              :shrink-child-roots (mapv rose/root (rose/children shrunk))
              :shrink-vector-root (rose/root shrinkv)
              :shrink-vector-child-roots (mapv rose/root (rose/children shrinkv))}))

(emit-case :auxiliary-generator-and-clojure-test-helpers
           (let [rng (rnd/make-random 1)
                 states (take 5 (gen/lazy-random-states rng))
                 nil-options (ct/process-options nil)
                 numeric-options (ct/process-options 7)
                 map-options (ct/process-options {:num-tests 3 :seed 11})]
             {:lazy-random-state-count (count states)
              :lazy-random-state-rand-longs? (every? number? (map rnd/rand-long states))
              :size-range-3 (vec (take 10 (gen/make-size-range-seq 3)))
              :sample-seq-count (count (take 5 (gen/sample-seq gen/nat 3)))
              :sample-seq-numbers? (every? number? (take 5 (gen/sample-seq gen/nat 3)))
              :process-nil-num-tests (:num-tests nil-options)
              :process-nil-reporter? (contains? nil-options :reporter-fn)
              :process-num (:num-tests numeric-options)
              :process-num-reporter? (contains? numeric-options :reporter-fn)
              :process-map-num-tests (:num-tests map-options)
              :process-map-seed (:seed map-options)
              :report-trials ct/*report-trials*
              :report-shrinking ct/*report-shrinking*
              :report-completion ct/*report-completion*
              :trial-report-period ct/*trial-report-period*}))

(emit-case :quick-check-shapes
           {:passing (result-summary
                      (tc/quick-check 40
                                      (prop/for-all [x (gen/choose -5 5)]
                                        (= x x))
                                      :seed 123))
            :failing (result-summary
                      (tc/quick-check 80
                                      (prop/for-all [x (gen/choose 0 50)]
                                        (< x 3))
                                      :seed 42))
            :exception (let [result (tc/quick-check
                                     5
                                     (prop/for-all [x (gen/return 1)]
                                       #?(:clj (/ x 0)
                                          :lpy (/ x 0)))
                                     :seed 5)
                             data (get-in result [:shrunk :result-data])]
                         {:pass? (:pass? result)
                          :has-clojure-error-key
                          (contains? data :clojure.test.check.properties/error)
                          :has-basilisp-error-key
                          (contains? data :basilisp.test.check.properties/error)})})
