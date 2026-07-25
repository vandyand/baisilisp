;; Direct semantic coverage for clojure.spec.gen.alpha/basilisp.spec.gen.alpha.
;;
;; Exact generated values are intentionally not compared. Clojure and Basilisp
;; use different RNG/test.check implementations, so this fixture compares
;; deterministic contracts: sample counts, predicates, bounds, public macro
;; metadata, lazy realization, named-generator loading, and property result
;; shapes.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as gen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn sample-valid?
  ([generator pred] (sample-valid? generator pred 12))
  ([generator pred n]
   (let [samples (gen/sample generator n)]
     {:count (count samples)
      :valid? (every? pred samples)})))

(defn generated-valid? [generator pred]
  (pred (gen/generate generator)))

(defn simple-value? [value]
  (or (nil? value)
      (boolean? value)
      (number? value)
      (char? value)
      (string? value)
      (keyword? value)
      (symbol? value)
      (uuid? value)))

(defn ascii-char? [value]
  (and (char? value) (< (int value) 128)))

(defn alpha-char? [value]
  (and (char? value) (boolean (re-matches #"[A-Za-z]" (str value)))))

(defn alphanumeric-char? [value]
  (and (char? value) (boolean (re-matches #"[A-Za-z0-9]" (str value)))))

(defn named-generator-loaded? []
  (boolean? (gen/generate (gen/gen-for-name 'clojure.test.check.generators/boolean))))

(defn thrown?* [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :default Exception) _
      true)))

(s/def :tests.spec-gen/age
       (s/with-gen (s/and int? #(<= 0 % 130))
                   #(gen/choose 0 130)))
(s/def :tests.spec-gen/name
       (s/with-gen string? #(gen/return "Ada")))
(s/def :tests.spec-gen/person
       (s/keys :req [:tests.spec-gen/age :tests.spec-gen/name]))

(emit-case :spec-gen-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.spec.gen.alpha
                                              :lpy 'basilisp.spec.gen.alpha))
                               %)
                   '[any
                     any-printable
                     bind
                     boolean
                     bytes
                     cat
                     char
                     char-alpha
                     char-alphanumeric
                     char-ascii
                     choose
                     delay
                     delay-impl
                     double
                     double*
                     elements
                     fmap
                     for-all*
                     frequency
                     gen-for-name
                     gen-for-pred
                     generate
                     hash-map
                     int
                     keyword
                     keyword-ns
                     large-integer
                     large-integer*
                     lazy-combinator
                     lazy-combinators
                     lazy-prim
                     lazy-prims
                     list
                     map
                     not-empty
                     one-of
                     quick-check
                     ratio
                     return
                     sample
                     set
                     shuffle
                     simple-type
                     simple-type-printable
                     string
                     string-alphanumeric
                     string-ascii
                     such-that
                     symbol
                     symbol-ns
                     tuple
                     uuid
                     vector
                     vector-distinct]))

(emit-case :primitive-generator-contracts
           {:any (sample-valid? (gen/any) any? 5)
            :any-printable (sample-valid? (gen/any-printable) any? 5)
            :boolean (sample-valid? (gen/boolean) boolean?)
            :bytes (sample-valid? (gen/bytes) bytes?)
            :char (sample-valid? (gen/char) char?)
            :char-alpha (sample-valid? (gen/char-alpha) alpha-char?)
            :char-alphanumeric (sample-valid? (gen/char-alphanumeric)
                                               alphanumeric-char?)
            :char-ascii (sample-valid? (gen/char-ascii) ascii-char?)
            :double (sample-valid? (gen/double) number?)
            :double-star (sample-valid? (gen/double* {:infinite? false :NaN? false})
                                        number?)
            :int (sample-valid? (gen/int) integer?)
            :large-integer (sample-valid? (gen/large-integer) integer?)
            :large-integer-star (sample-valid? (gen/large-integer* {:min 5 :max 12})
                                               #(<= 5 % 12))
            :ratio (sample-valid? (gen/ratio) number?)
            :simple-type (sample-valid? (gen/simple-type) simple-value?)
            :simple-type-printable (sample-valid? (gen/simple-type-printable)
                                                  simple-value?)
            :string (sample-valid? (gen/string) string?)
            :string-alphanumeric (sample-valid? (gen/string-alphanumeric) string?)
            :string-ascii (sample-valid? (gen/string-ascii)
                                         #(and (string? %)
                                               (every? (fn [c] (< (int c) 128)) %)))
            :keyword (sample-valid? (gen/keyword)
                                    #(and (keyword? %) (nil? (namespace %))))
            :keyword-ns (sample-valid? (gen/keyword-ns)
                                       #(and (keyword? %) (some? (namespace %))))
            :symbol (sample-valid? (gen/symbol)
                                   #(and (symbol? %) (nil? (namespace %))))
            :symbol-ns (sample-valid? (gen/symbol-ns)
                                      #(and (symbol? %) (some? (namespace %))))
            :uuid (sample-valid? (gen/uuid) uuid?)})

(emit-case :combinator-contracts
           {:bind (generated-valid? (gen/bind (gen/return 3)
                                              #(gen/return (inc %)))
                                    #(= 4 %))
            :cat (sample-valid? (gen/cat (gen/return [1 2])
                                         (gen/return '(3 4)))
                                #(= [1 2 3 4] (vec %))
                                8)
            :choose (sample-valid? (gen/choose 2 6) #(<= 2 % 6))
            :elements (sample-valid? (gen/elements [:a :b :c]) #{:a :b :c})
            :fmap (sample-valid? (gen/fmap inc (gen/choose 1 4)) #(<= 2 % 5))
            :frequency (sample-valid? (gen/frequency [[1 (gen/return :a)]
                                                      [3 (gen/return :b)]])
                                      #{:a :b})
            :hash-map (sample-valid? (gen/hash-map :a (gen/int)
                                                   :b (gen/string))
                                     #(and (map? %)
                                           (integer? (:a %))
                                           (string? (:b %))))
            :list (sample-valid? (gen/list (gen/int)) #(every? integer? %))
            :map (sample-valid? (gen/map (gen/keyword) (gen/int))
                                #(and (map? %)
                                      (every? keyword? (keys %))
                                      (every? integer? (vals %))))
            :not-empty (sample-valid? (gen/not-empty (gen/vector (gen/int)))
                                      #(and (vector? %) (seq %)))
            :one-of (sample-valid? (gen/one-of [(gen/return :a)
                                                (gen/return :b)])
                                   #{:a :b})
            :return (generated-valid? (gen/return :constant) #(= :constant %))
            :set (sample-valid? (gen/set (gen/int)) #(and (set? %)
                                                          (every? integer? %)))
            :shuffle (sample-valid? (gen/shuffle [1 2 3])
                                    #(= #{1 2 3} (set %)))
            :such-that (sample-valid? (gen/such-that integer? (gen/choose 0 20))
                                      integer?)
            :tuple (sample-valid? (gen/tuple (gen/int) (gen/string))
                                  #(and (vector? %)
                                        (= 2 (count %))
                                        (integer? (first %))
                                        (string? (second %))))
            :vector (sample-valid? (gen/vector (gen/int)) #(every? integer? %))
            :vector-distinct (sample-valid? (gen/vector-distinct
                                             (gen/choose 0 10))
                                            #(= (count %) (count (distinct %))))})

(emit-case :spec-alpha-generator-overrides-and-with-gen
           (let [named-samples (gen/sample
                                (s/gen :tests.spec-gen/person
                                       {:tests.spec-gen/age #(gen/return 42)
                                        :tests.spec-gen/name #(gen/return "Ada")})
                                20)
                 tuple-spec    (s/tuple int? string? keyword?)
                 path-samples  (gen/sample
                                (s/gen tuple-spec
                                       {[0] #(gen/return 7)
                                        [1] #(gen/return "path")})
                                20)
                 regex-spec    (s/cat :age int? :label string?)
                 regex-samples (gen/sample
                                (s/gen regex-spec
                                       {[:age] #(gen/return 9)
                                        [:label] #(gen/return "regex")})
                                20)]
             {:named-count (count named-samples)
              :named-overrides? (every? #(and (= 42 (:tests.spec-gen/age %))
                                              (= "Ada" (:tests.spec-gen/name %))
                                              (s/valid? :tests.spec-gen/person %))
                                        named-samples)
              :path-count (count path-samples)
              :path-overrides? (every? #(and (= 7 (first %))
                                             (= "path" (second %))
                                             (s/valid? tuple-spec %))
                                       path-samples)
              :regex-path-count (count regex-samples)
              :regex-path-overrides? (every? #(and (= 9 (first %))
                                                   (= "regex" (second %))
                                                   (s/valid? regex-spec %))
                                             regex-samples)
              :invalid-override-rejected?
              (thrown?* (fn []
                          (gen/generate
                           (s/gen int? {int? #(gen/return "not-an-integer")})
                           10
                           4)))}))

(emit-case :spec-alpha-regex-repeat-generation-diversity
           (let [token     (s/with-gen int? #(gen/elements [1 2 3 4]))
                 star-spec (s/* token)
                 plus-spec (s/+ token)
                 stars     (gen/sample (s/gen star-spec) 80)
                 pluses    (gen/sample (s/gen plus-spec) 80)]
             {:star-count (count stars)
              :star-every-valid? (every? #(s/valid? star-spec %) stars)
              :star-some-empty? (boolean (some empty? stars))
              :star-some-nonempty? (boolean (some seq stars))
              :plus-count (count pluses)
              :plus-every-valid? (every? #(s/valid? plus-spec %) pluses)
              :plus-all-nonempty? (every? seq pluses)
              :plus-some-longer-than-min? (boolean (some #(> (count %) 1)
                                                         pluses))}))

(emit-case :lazy-and-named-generator-contracts
           (let [hits       (atom 0)
                 delayed    (gen/delay-impl (delay (swap! hits inc)
                                                   (gen/return :delayed)))
                 delay-impl-before @hits
                 delay-impl-generated (gen/generate delayed)
                 delay-impl-after @hits
                 macro-hits (atom 0)
                 macro-gen  (gen/delay (swap! macro-hits inc)
                                       (gen/return :macro-delayed))
                 delay-before @macro-hits
                 delay-generated (gen/generate macro-gen)
                 delay-after @macro-hits]
             {:delay-impl-before delay-impl-before
              :delay-impl-generated delay-impl-generated
              :delay-impl-after delay-impl-after
              :delay-before delay-before
              :delay-generated delay-generated
              :delay-after delay-after
              :gen-for-name (named-generator-loaded?)
              :gen-for-pred-int (sample-valid? (gen/gen-for-pred int?) integer?)
              :gen-for-pred-set (sample-valid? (gen/gen-for-pred #{:x :y})
                                               #{:x :y})
              :gen-for-pred-unknown? (nil? (gen/gen-for-pred (fn [_] true)))
              :lazy-macro-vars [(boolean (:macro (meta #'gen/lazy-prim)))
                                (boolean (:macro (meta #'gen/lazy-prims)))
                                (boolean (:macro (meta #'gen/lazy-combinator)))
                                (boolean (:macro (meta #'gen/lazy-combinators)))]}))

(emit-case :lazy-macro-expansion-contracts
           {:lazy-prim #?(:clj (sample-valid? (gen/int) integer?)
                          :lpy (do
                                 (gen/lazy-prim int)
                                 (sample-valid? (int) integer?)))
            :lazy-prims #?(:clj [(sample-valid? (gen/boolean) boolean?)
                                 (sample-valid? (gen/string) string?)]
                           :lpy (do
                                  (gen/lazy-prims boolean string)
                                  [(sample-valid? (boolean) boolean?)
                                   (sample-valid? (string) string?)]))
            :lazy-combinator #?(:clj (sample-valid? (gen/vector (gen/return :x) 2)
                                                    #(= [:x :x] %))
                                 :lpy (do
                                        (gen/lazy-combinator vector)
                                        (sample-valid? (vector (gen/return :x) 2)
                                                       #(= [:x :x] %))))
            :lazy-combinators #?(:clj [(generated-valid? (gen/return :constant)
                                                         #(= :constant %))
                                       (sample-valid? (gen/tuple (gen/int)
                                                                 (gen/string))
                                                      #(and (vector? %)
                                                            (= 2 (count %))
                                                            (integer? (first %))
                                                            (string? (second %))))]
                                  :lpy (do
                                         (gen/lazy-combinators return tuple)
                                         [(generated-valid? (return :constant)
                                                           #(= :constant %))
                                          (sample-valid? (tuple (gen/int)
                                                               (gen/string))
                                                        #(and (vector? %)
                                                              (= 2 (count %))
                                                              (integer? (first %))
                                                              (string? (second %))))]))})

(emit-case :property-contracts
           (let [passing (gen/quick-check
                          20
                          (gen/for-all* [(gen/choose 0 10)]
                                        (fn [x] (<= 0 x 10))))
                 failing (gen/quick-check
                          20
                          (gen/for-all* [(gen/return 1)]
                                        (fn [x] (zero? x))))]
             {:passing-result (:result passing)
              :passing-tests-positive? (pos? (:num-tests passing))
              :failing-result (:result failing)
              :failing-has-fail? (contains? failing :fail)
              :failing-tests-positive? (pos? (:num-tests failing))}))
