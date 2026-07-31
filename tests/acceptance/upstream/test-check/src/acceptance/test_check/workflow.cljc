(ns acceptance.test-check.workflow
  (:require [clojure.test :as test]
            [clojure.test.check :as tc]
            [clojure.test.check.clojure-test.assertions :as assertions]
            [clojure.test.check.clojure-test.assertions.cljs :as assertions-cljs]
            [clojure.test.check.clojure-test :as ct]
            [clojure.test.check.generators :as gen]
            [clojure.test.check.impl :as impl]
            [clojure.test.check.properties :as prop]
            [clojure.test.check.random :as rnd]
            [clojure.test.check.results :as results]
            [clojure.test.check.rose-tree :as rose]))

(def ascii-printable
  (set (map str " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~")))

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(def portable-generator-names
  '[->Generator any any-equatable any-printable
    any-printable-equatable big-ratio bind boolean byte bytes call-gen char
    char-alpha char-alpha-numeric char-alphanumeric char-ascii choose
    container-type double double* elements fmap frequency gen-bind gen-fmap
    gen-pure generate generator? hash-map int keyword keyword-ns large-integer
    large-integer* lazy-random-states let list list-distinct list-distinct-by
    make-size-range-seq map map->Generator nat neg-int no-shrink not-empty
    one-of pos-int ratio recursive-gen resize return s-neg-int s-pos-int sample
    sample-seq scale set shrink-2 shuffle simple-type simple-type-equatable
    simple-type-printable simple-type-printable-equatable size-bounded-bigint
    sized small-integer sorted-set string string-alpha-numeric
    string-alphanumeric string-ascii such-that symbol symbol-ns tuple uuid
    vector vector-distinct vector-distinct-by])

(defn has-publics? [ns-sym names]
  (let [publics (ns-publics ns-sym)]
    (every? #(contains? publics %) names)))

(defn public-summary []
  {:root (has-publics? 'clojure.test.check '[quick-check])
   :generators (has-publics? 'clojure.test.check.generators
                             portable-generator-names)
   :properties (has-publics? 'clojure.test.check.properties
                             '[->ErrorResult for-all for-all*
                               map->ErrorResult])
   :random (has-publics? 'clojure.test.check.random
                         '[->JavaUtilSplittableRandom IRandom
                           make-java-util-splittable-random make-random
                           rand-double rand-long split split-n])
   :results (has-publics? 'clojure.test.check.results
                          '[pass? result-data])
   :rose-tree (has-publics? 'clojure.test.check.rose-tree
                            '[->RoseTree bind children collapse filter fmap
                              join make-rose permutations pure remove root seq
                              shrink shrink-vector zip])
   :clojure-test (has-publics? 'clojure.test.check.clojure-test
                               '[*default-opts* *default-test-count*
                                 *report-completion* *report-shrinking*
                                 *report-trials* *trial-report-period*
                                 assert-check default-reporter-fn defspec
                                 process-options trial-report-dots
                                 trial-report-periodic with-test-out*])
   :assertions (has-publics?
                'clojure.test.check.clojure-test.assertions
                '[check-results check? file-and-line* test-context-stacktrace])
   :assertions-cljs (empty?
                     (ns-publics
                      'clojure.test.check.clojure-test.assertions.cljs))
   :impl (has-publics? 'clojure.test.check.impl
                       '[get-current-time-millis])})

(defn sample-ok? [pred generator n]
  (every? pred (gen/sample generator n)))

(defn generated-ok? [pred generator size seed]
  (pred (gen/generate generator size seed)))

(defn result-shape [result]
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

(defn error-result-key? [m]
  (or (contains? m :clojure.test.check.properties/error)
      (contains? m :basilisp.test.check.properties/error)))

(defn primitive-generator-summary []
  {:types [#?(:clj true :lpy (some? gen/Generator))
           (gen/generator? gen/nat)
           (gen/generator? (gen/->Generator (fn [_ size]
                                              (rose/pure size))))
           (gen/generator? (gen/map->Generator
                            {:gen (fn [_ size] (rose/pure size))}))]
   :integer [(sample-ok? integer? gen/nat 24)
             (sample-ok? #(<= -2147483648 % 2147483647) gen/int 24)
             (sample-ok? #(<= -128 % 127) gen/byte 24)
             (sample-ok? pos? gen/pos-int 24)
             (sample-ok? neg? gen/neg-int 24)
             (sample-ok? pos? gen/s-pos-int 24)
             (sample-ok? neg? gen/s-neg-int 24)
             (sample-ok? integer? gen/small-integer 24)
             (sample-ok? integer? gen/large-integer 24)
             (sample-ok? integer? (gen/large-integer* {}) 24)
             (sample-ok? integer? gen/size-bounded-bigint 24)]
   :numeric [(sample-ok? float? gen/double 24)
             (sample-ok? float? (gen/double* {}) 24)
             (sample-ok? number? gen/ratio 24)
             (sample-ok? number? gen/big-ratio 24)]
   :scalar [(sample-ok? boolean? gen/boolean 24)
            (sample-ok? any? gen/any 16)
            (sample-ok? any? gen/any-equatable 16)
            (sample-ok? any? gen/any-printable 16)
            (sample-ok? any? gen/any-printable-equatable 16)
            (sample-ok? any? gen/simple-type 24)
            (sample-ok? any? gen/simple-type-equatable 24)
            (sample-ok? any? gen/simple-type-printable 24)
            (sample-ok? any? gen/simple-type-printable-equatable 24)]
   :text [(sample-ok? #(or (nil? %) (char? %)) gen/char 24)
          (sample-ok? #(contains? ascii-printable (str %)) gen/char-ascii 24)
          (sample-ok? #(or (nil? %) (char? %)) gen/char-alpha 24)
          (sample-ok? #(or (nil? %) (char? %)) gen/char-alpha-numeric 24)
          (sample-ok? #(or (nil? %) (char? %)) gen/char-alphanumeric 24)
          (sample-ok? string? gen/string 24)
          (sample-ok? #(every? (fn [ch] (contains? ascii-printable (str ch)))
                               %)
                      gen/string-ascii
                      24)
          (sample-ok? string? gen/string-alpha-numeric 24)
          (sample-ok? string? gen/string-alphanumeric 24)
          (sample-ok? keyword? gen/keyword 24)
          (sample-ok? keyword? gen/keyword-ns 24)
          (sample-ok? symbol? gen/symbol 24)
          (sample-ok? symbol? gen/symbol-ns 24)
          (sample-ok? uuid? gen/uuid 12)]
   :bytes (sample-ok? bytes? gen/bytes 12)})

(defn collection-generator-summary []
  {:list [(sample-ok? sequential? (gen/list gen/nat) 24)
          (sample-ok? #(= (count %) (count (set %)))
                      (gen/list-distinct gen/nat)
                      24)
          (sample-ok? #(= (count %) (count (set (map abs %))))
                      (gen/list-distinct-by abs (gen/choose -20 20))
                      24)]
   :vector [(sample-ok? vector? (gen/vector gen/nat) 24)
            (sample-ok? #(= 3 (count %))
                        (gen/vector (gen/choose 0 9) 3)
                        24)
            (sample-ok? #(<= 2 (count %) 5)
                        (gen/vector (gen/choose 0 9) 2 5)
                        24)
            (sample-ok? #(and (<= 3 (count %) 8)
                              (= (count %) (count (set %))))
                        (gen/vector-distinct (gen/choose 0 100)
                                             {:min-elements 3
                                              :max-elements 8})
                        24)
            (sample-ok? #(= (count %) (count (set (map abs %))))
                        (gen/vector-distinct-by abs (gen/choose -20 20))
                        24)]
   :map-set [(sample-ok? map?
                         (gen/hash-map :a gen/nat :b gen/boolean)
                         24)
             (sample-ok? map?
                         (gen/map gen/keyword gen/small-integer
                                  {:max-elements 5})
                         24)
             (sample-ok? set?
                         (gen/set gen/small-integer {:max-elements 5})
                         24)
             (sample-ok? set? (gen/sorted-set gen/small-integer) 24)]
   :not-empty (sample-ok? seq (gen/not-empty (gen/vector gen/nat)) 24)})

(defn combinator-summary []
  (let [size-generator (gen/sized (fn [size] (gen/return size)))
        recursive (gen/recursive-gen
                   (fn [inner]
                     (gen/one-of [(gen/vector inner 0 2)
                                  gen/small-integer]))
                   gen/small-integer)
        bound (gen/bind (gen/choose 1 5)
                        (fn [n]
                          (gen/fmap (fn [xs] [n xs])
                                    (gen/vector gen/nat n))))
        gen-let (gen/let [n (gen/choose 1 5)
                          xs (gen/vector gen/nat n)]
                  [n xs])]
    {:constructors [(gen/generator? (gen/elements [:a :b :c]))
                    (gen/generator? (gen/frequency [[2 gen/nat]
                                                    [1 gen/boolean]]))
                    (gen/generator? (gen/gen-pure :x))
                    (gen/generator? (gen/gen-fmap inc gen/nat))
                    (gen/generator? (gen/gen-bind gen/nat
                                                  (fn [_] gen/boolean)))
                    (gen/generator? (gen/one-of [gen/nat gen/boolean]))
                    (gen/generator? (gen/container-type gen/nat))
                    (gen/generator? (gen/shuffle [1 2 3]))
                    (gen/generator? recursive)]
     :sizing [(= 9 (gen/generate size-generator 9 123))
              (= 10 (gen/generate (gen/scale inc size-generator) 9 123))
              (= 4 (gen/generate (gen/resize 4 size-generator) 9 123))]
     :composition [(sample-ok? even?
                               (gen/fmap #(* 2 %) (gen/choose 0 20))
                               24)
                   (sample-ok? #(= (first %) (count (second %))) bound 24)
                   (sample-ok? #(= (first %) (count (second %))) gen-let 24)
                   (sample-ok? pos?
                               (gen/such-that pos?
                                              (gen/choose -20 20)
                                              {:max-tries 100})
                               24)
                   (sample-ok? #(= 3 (count %))
                               (gen/tuple gen/nat gen/boolean gen/string)
                               24)]
     :no-shrink [(some? (rose/root
                         (gen/call-gen (gen/no-shrink gen/nat)
                                       (rnd/make-random 123)
                                       10)))
                 (some? (rose/root
                         (gen/call-gen (gen/shrink-2 gen/small-integer)
                                       (rnd/make-random 123)
                                       10)))]}))

(defn random-rose-summary []
  (let [rng (rnd/make-random 123)
        rng2 (rnd/make-java-util-splittable-random 123)
        rng3 (rnd/->JavaUtilSplittableRandom 1 2)
        split-pair (rnd/split rng)
        split-many (rnd/split-n rng 4)
        t1 (rose/make-rose 1 [(rose/pure 10) (rose/pure 11)])
        t2 (rose/make-rose 2 [(rose/pure 20)])
        t3 (rose/make-rose 3 [])
        roses [t1 t2 t3]
        tree (rose/make-rose :root
                             [(rose/make-rose :a [(rose/pure :aa)])
                              (rose/pure :b)])
        joined (rose/join (rose/pure (rose/pure :joined)))
        bound (rose/bind (rose/pure 1) #(rose/pure (inc %)))
        filtered (rose/filter odd? (rose/make-rose 1 [(rose/pure 2)
                                                       (rose/pure 3)]))
        zipped (rose/zip vector roses)
        shrunk (rose/shrink vector roses)
        shrinkv (rose/shrink-vector vector roses)]
    {:random [(some? rnd/IRandom)
              #?(:clj true :lpy (some? rnd/JavaUtilSplittableRandom))
              (number? (rnd/rand-long rng))
              (float? (rnd/rand-double rng))
              (= 2 (count split-pair))
              (= 4 (count split-many))
              (every? number? (map rnd/rand-long split-many))
              (number? (rnd/rand-long rng2))
              (number? (rnd/rand-long rng3))]
     :rose-basic [#?(:clj true :lpy (some? rose/RoseTree))
                  (= :joined (rose/root joined))
                  (= 2 (rose/root bound))
                  (= 1 (rose/root filtered))
                  (every? odd? (map rose/root (rose/children filtered)))]
     :rose-shapes {:seq-count (count (vec (rose/seq tree)))
                   :collapse-root (rose/root (rose/collapse tree))
                   :collapse-child-count (count (rose/children
                                                 (rose/collapse tree)))
                   :permutation-count (count (rose/permutations roses))
                   :remove-count (count (rose/remove roses))
                   :zip-root-count (count (rose/root zipped))
                   :zip-child-count (count (rose/children zipped))
                   :shrink-root-count (count (rose/root shrunk))
                   :shrink-child-count (count (rose/children shrunk))
                   :shrink-vector-root-count (count (rose/root shrinkv))
                   :shrink-vector-child-count (count (rose/children shrinkv))}}))

(defn property-summary []
  (let [passing (tc/quick-check 40
                                (prop/for-all [x (gen/choose -5 5)]
                                  (= x x))
                                :seed 123)
        failing (tc/quick-check 80
                                (prop/for-all [x (gen/choose 0 50)]
                                  (< x 3))
                                :seed 42)
        exception-result (tc/quick-check
                          5
                          (prop/for-all [x (gen/return 1)]
                            #?(:clj (/ x 0)
                               :lpy (/ x 0)))
                          :seed 5)
        error-result (prop/->ErrorResult :boom)
        mapped-error (prop/map->ErrorResult {:error :mapped})
        prop-result (gen/call-gen
                     (prop/for-all* [gen/nat] (fn [x] (= x x)))
                     (rnd/make-random 123)
                     3)]
    {:results [(some? results/Result)
               (satisfies? results/Result true)
               (not (results/pass? error-result))
               (not (results/pass? mapped-error))
               (error-result-key? (results/result-data error-result))
               (results/pass? (rose/root prop-result))]
     :quick-check {:passing (result-shape passing)
                   :failing (result-shape failing)
                   :exception {:pass? (:pass? exception-result)
                               :has-error-key (error-result-key?
                                               (get-in exception-result
                                                       [:shrunk
                                                        :result-data]))}}}))

(ct/defspec generated-defspec-contract 1
  (prop/for-all [x gen/nat] (= x x)))

(defn clojure-test-summary []
  (let [before (impl/get-current-time-millis)
        check-form (assertions/check? nil
                                      '(clojure.test.check.clojure-test/check?
                                        {:pass? true}))
        report-result (assertions/check-results {:pass? true
                                                 :result true
                                                 :num-tests 1})
        after (impl/get-current-time-millis)
        nil-options (ct/process-options nil)
        numeric-options (ct/process-options 7)
        map-options (ct/process-options {:num-tests 3 :seed 11})]
    {:defaults [(number? ct/*default-test-count*)
                (map? ct/*default-opts*)
                (boolean? ct/*report-trials*)
                (boolean? ct/*report-shrinking*)
                (boolean? ct/*report-completion*)
                (number? ct/*trial-report-period*)]
     :options {:nil-num-tests (:num-tests nil-options)
               :nil-reporter? (contains? nil-options :reporter-fn)
               :num (:num-tests numeric-options)
               :num-reporter? (contains? numeric-options :reporter-fn)
               :map-num-tests (:num-tests map-options)
               :map-seed (:seed map-options)}
     :assertions [(sequential? (assertions/test-context-stacktrace []))
                  (= {:file nil :line nil}
                     (assertions/file-and-line* []))
                  (seq? check-form)
                  (nil? report-result)]
     :impl-time [(integer? before)
                 (integer? after)
                 (<= before after)]
     :defspec (and (some? #'ct/defspec)
                   (some? #'generated-defspec-contract))
     :cljs-empty (empty? (ns-publics
                          'clojure.test.check.clojure-test.assertions.cljs))
     :trial-helpers [(fn? ct/default-reporter-fn)
                     (fn? ct/trial-report-dots)
                     (fn? ct/trial-report-periodic)
                     (fn? ct/with-test-out*)
                     (try
                       (ct/assert-check {:pass? true})
                       true
                       (catch #?(:clj Throwable :lpy python/Exception) _
                         false))]}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn generated-case [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)
        bound (inc (mod s1 50))
        min-size (mod s2 4)
        max-size (+ min-size (mod s3 8))
        vector-gen (gen/vector (gen/choose 0 bound) min-size max-size)
        distinct-gen (gen/vector-distinct (gen/choose 0 200)
                                          {:min-elements 0
                                           :max-elements max-size})
        prop-result (tc/quick-check
                     10
                     (prop/for-all [xs vector-gen]
                       (and (<= min-size (count xs) max-size)
                            (every? #(<= 0 % bound) xs)))
                     :seed seed)]
    {:seed seed
     :bound bound
     :min-size min-size
     :max-size max-size
     :vector-invariant (sample-ok? #(and (<= min-size (count %) max-size)
                                         (every? (fn [x] (<= 0 x bound)) %))
                                   vector-gen
                                   10)
     :distinct-invariant (sample-ok? #(= (count %) (count (set %)))
                                     distinct-gen
                                     10)
     :generated-choice-ok? (generated-ok? #(<= 0 % bound)
                                          (gen/choose 0 bound)
                                          max-size
                                          seed)
     :property-shape (result-shape prop-result)
     :next-seed s3}))

(defn generated-summary []
  {:cases (loop [remaining 48
                 seed 253635900
                 result []]
            (if (zero? remaining)
              result
              (let [case (generated-case seed)]
                (recur (dec remaining)
                       (:next-seed case)
                       (conj result (dissoc case :next-seed))))))
   :adversarial [(error? #(gen/elements []))
                 (error? #(gen/frequency []))
                 (error? #(gen/one-of []))
                 (error? #(gen/vector gen/nat 5 2))
                 (error? #(gen/such-that (constantly false)
                                         gen/nat
                                         {:max-tries 3}))
                 (error? #(ct/process-options :bad-options))
                 (error? #(ct/assert-check
                           {:pass? false
                            :result-data
                            {:clojure.test.check.properties/error
                             #?(:clj (RuntimeException. "boom")
                                :lpy (python/Exception "boom"))}}))]})
