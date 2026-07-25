;; Portable clojure.spec.alpha semantic contracts.
;;
;; Keep outputs restricted to portable EDN values.  Avoid printing opaque spec
;; and generator objects directly; normalize those to booleans, counts, or
;; generated sample values.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.gen.alpha :as gen])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _
      true)))

(defn inc1 [x] (inc x))
(defn dec1 [x] (dec x))

(def problems-key #?(:clj :clojure.spec.alpha/problems
                     :lpy :basilisp.spec.alpha/problems))

(s/fdef inc1 :args (s/cat :x int?) :ret int?)
(s/def :tests.spec-alpha/name string?)
(s/def :tests.spec-alpha/age int?)
(s/def :tests.spec-alpha/flag boolean?)

(emit-case :core-contracts
           {:spec? (boolean (s/spec? (s/spec int?)))
            :regex? [(boolean (s/regex? (s/cat :x int?)))
                     (boolean (s/regex? (s/spec int?)))]
            :valid [(s/valid? int? 1)
                    (s/valid? int? "x")]
            :conform [(s/conform int? 1)
                      (s/invalid? (s/conform int? "x"))]
            :unform (s/unform int? 1)
            :form? (boolean (s/form (s/spec int?)))
            :describe? (boolean (s/describe (s/spec int?)))
            :abbrev (s/abbrev '(clojure.core/fn [x] x))})

(emit-case :registry-contracts
           (let [defined (s/def :tests.spec-alpha/id int?)
                 fetched (boolean (s/get-spec :tests.spec-alpha/id))
                 registered (contains? (s/registry) :tests.spec-alpha/id)]
             {:def defined
              :get fetched
              :registry registered}))

(emit-case :composition-contracts
           {:and [(s/valid? (s/and int? pos?) 2)
                  (s/valid? (s/and int? pos?) -1)]
            :or [(s/conform (s/or :s string? :i int?) "x")
                 (s/conform (s/or :s string? :i int?) 2)
                 (s/invalid? (s/conform (s/or :s string? :i int?) :x))]
            :nilable [(s/valid? (s/nilable string?) nil)
                      (s/valid? (s/nilable string?) "x")
                      (s/valid? (s/nilable string?) 1)]
            :nonconforming (s/conform (s/nonconforming (s/or :s string? :i int?)) 2)
            :conformer [(s/conform (s/conformer #(if (string? %) (keyword %) ::s/invalid)
                                                name)
                                    "ok")
                        (s/unform (s/conformer #(if (string? %) (keyword %) ::s/invalid)
                                                name)
                                  :ok)]})

(emit-case :collection-contracts
           {:coll [(s/conform (s/coll-of int? :kind vector? :count 2) [1 2])
                   (s/invalid? (s/conform (s/coll-of int? :kind vector? :count 2) [1]))]
            :every [(s/conform (s/every int? :kind vector? :min-count 1) [1 2])
                    (s/invalid? (s/conform (s/every int? :kind vector? :min-count 1) []))]
            :every-kv [(s/valid? (s/every-kv keyword? int?) {:a 1})
                       (s/valid? (s/every-kv keyword? int?) {"a" 1})]
            :map-of [(s/valid? (s/map-of keyword? int?) {:a 1})
                     (s/valid? (s/map-of keyword? int?) {:a "x"})]
            :keys [(s/valid? (s/keys :req [:tests.spec-alpha/name]
                                      :opt [:tests.spec-alpha/age])
                              {:tests.spec-alpha/name "Ada"
                               :tests.spec-alpha/age 42})
                   (s/valid? (s/keys :req-un [:tests.spec-alpha/name])
                              {:name "Ada"})]
            :keys* [(s/conform (s/keys* :req-un [:tests.spec-alpha/name])
                               [:name "Ada"])
                    (s/invalid? (s/conform (s/keys* :req-un [:tests.spec-alpha/name])
                                           [:name 1]))]
            :tuple [(s/conform (s/tuple int? string?) [1 "x"])
                    (s/invalid? (s/conform (s/tuple int? string?) [1 2]))]
            :merge (s/valid? (s/merge (s/keys :req [:tests.spec-alpha/name])
                                      (s/keys :req [:tests.spec-alpha/age]))
                             {:tests.spec-alpha/name "Ada"
                              :tests.spec-alpha/age 42})})

(emit-case :regex-contracts
           {:cat (s/conform (s/cat :name string? :age int?) ["Ada" 42])
            :alt [(s/conform (s/alt :name string? :age int?) [42])
                  (s/unform (s/alt :name string? :age int?) [:age 42])]
            :star (s/conform (s/* int?) [1 2 3])
            :plus [(s/conform (s/+ int?) [1 2])
                   (s/invalid? (s/conform (s/+ int?) []))]
            :maybe [(s/conform (s/? int?) [])
                    (s/conform (s/? int?) [1])
                    (s/invalid? (s/conform (s/? int?) [1 2]))]
            :amp [(s/conform (s/& (s/+ int?) #(< (count %) 3)) [1 2])
                  (s/invalid? (s/conform (s/& (s/+ int?) #(< (count %) 3))
                                         [1 2 3]))]})

(def range-start #inst "2020-01-01T00:00:00.000-00:00")
(def range-mid #inst "2020-01-01T12:00:00.000-00:00")
(def range-end #inst "2020-01-02T00:00:00.000-00:00")

(emit-case :range-contracts
           {:int-in [(s/int-in-range? 0 3 2)
                     (s/int-in-range? 0 3 3)
                     (s/valid? (s/int-in 0 3) 2)
                     (s/valid? (s/int-in 0 3) 3)]
            :double-in [(s/valid? (s/double-in :NaN? false
                                               :infinite? false
                                               :min 0.0
                                               :max 1.0)
                                  0.5)
                        (s/valid? (s/double-in :NaN? false
                                               :infinite? false
                                               :min 0.0
                                               :max 1.0)
                                  2.0)]
            :inst-in [(s/inst-in-range? range-start range-end range-mid)
                      (s/inst-in-range? range-start range-end range-end)
                      (s/valid? (s/inst-in range-start range-end) range-mid)
                      (s/valid? (s/inst-in range-start range-end) range-end)]})

(emit-case :assert-and-explain-contracts
           (let [_ (s/check-asserts true)
                 assert-pass (s/assert int? 1)
                 assert-star-pass (s/assert* int? 2)
                 assert-fail (rejected? #(s/assert int? "x"))
                 assert-star-fail (rejected? #(s/assert* int? "x"))
                 ed (s/explain-data int? "x")
                 _ (s/check-asserts false)]
             {:assert-pass assert-pass
              :assert-star-pass assert-star-pass
              :assert-fail assert-fail
              :assert-star-fail assert-star-fail
              :check-reset (not (s/check-asserts?))
              :explain-data (boolean ed)
              :explain-data-shape
              [(contains? ed #?(:clj :clojure.spec.alpha/problems
                                :lpy :basilisp.spec.alpha/problems))
               (contains? ed #?(:clj :clojure.spec.alpha/spec
                                :lpy :basilisp.spec.alpha/spec))
               (contains? ed #?(:clj :clojure.spec.alpha/value
                                :lpy :basilisp.spec.alpha/value))]
              :explain-str (boolean (seq (s/explain-str int? "x")))
              :explain-printer-callable (ifn? s/explain-printer)
              :explain-out-callable (ifn? s/explain-out)}))

(emit-case :public-control-var-contracts
           (let [registered #?(:clj (do
                                      (s/fdef dec1
                                        :args (s/cat :x int?)
                                        :ret int?)
                                      true)
                               :lpy (boolean
                                     (s/fdef* (var dec1)
                                              (s/cat :x int?)
                                              int?
                                              nil)))
                 fspec-found #?(:clj (boolean (s/get-spec `dec1))
                                :lpy (boolean (s/get-fspec (var dec1))))
                 explanation (binding [s/*explain-out* (fn [_] (print "explained"))]
                               (with-out-str (s/explain int? "x")))]
             {:dynamic-vars [s/*compile-asserts*
                             s/*recursion-limit*
                             s/*fspec-iterations*
                             s/*coll-check-limit*
                             s/*coll-error-limit*
                             (ifn? s/*explain-out*)]
              :protocol-vars [(boolean s/Spec)
                              (boolean s/Specize)]
              :invalid-sentinel? (s/invalid? #?(:clj ::s/invalid
                                                 :lpy s/invalid))
              :fdef-registered? registered
              :fspec-found? fspec-found
              :explain-emits? (boolean (seq explanation))}))

(emit-case :generator-and-fspec-contracts
           {:gen-valid-samples (every? #(s/valid? int? %)
                                       (take 5 (gen/sample
                                                (s/gen (s/with-gen int?
                                                         #(gen/choose 0 3))))))
            :exercise (count (s/exercise (s/with-gen int? #(gen/choose 0 3)) 3))
            :exercise-fn (count (s/exercise-fn `inc1 3))
            :fspec-valid [(s/valid? (s/fspec :args (s/cat :x int?) :ret int?) inc1)
                          (s/valid? (s/fspec :args (s/cat :x int?) :ret int?) 42)]})

(emit-case :protocol-helper-contracts
           (let [sp (s/spec int?)]
             {:conform* (s/conform* sp 1)
              :unform* (s/unform* sp 1)
              :explain* (boolean (s/explain* sp [] [] [] "x"))
              :describe* (boolean (s/describe* sp))
              :gen* (boolean (s/gen* sp nil [] {}))
              :with-gen* (boolean (s/with-gen* sp #(gen/choose 0 3)))
              :specize* (boolean (s/spec? (s/specize* int?)))}))

(emit-case :impl-helper-contracts
           (let [from-def (s/def-impl :tests.spec-alpha/from-def 'int? int?)]
             {:callable [(ifn? s/spec-impl)
                         (ifn? s/and-spec-impl)
                         (ifn? s/or-spec-impl)
                         (ifn? s/nilable-impl)
                         (ifn? s/every-impl)
                         (ifn? s/map-spec-impl)
                         (ifn? s/tuple-impl)
                         (ifn? s/regex-spec-impl)
                         (ifn? s/amp-impl)
                         (ifn? s/rep-impl)
                         (ifn? s/rep+impl)
                         (ifn? s/maybe-impl)
                         (ifn? s/merge-spec-impl)
                         (ifn? s/multi-spec-impl)
                         (ifn? s/fspec-impl)]
              :def-impl [from-def (s/valid? :tests.spec-alpha/from-def 1)]
              :cat-impl (s/conform (s/cat-impl [:x] [int?] ['int?]) [1])
              :alt-impl (s/conform (s/alt-impl [:i] [int?] ['int?]) [1])
              :rep+impl (s/conform (s/rep+impl 'int? int?) [1 2])
              :maybe-impl (s/conform (s/maybe-impl int? 'int?) [])}))

(emit-case :adversarial-conform-explain-and-regex
           (let [string->keyword (s/conformer #(if (string? %)
                                                 (keyword %)
                                                 #?(:clj ::s/invalid
                                                    :lpy s/invalid))
                                              name)
                 chained (s/and string->keyword keyword?)
                 branch-order (s/or :int int? :positive (s/and int? pos?))
                 greedy-tail (s/cat :head (s/* int?) :tail string?)
                 greedy-last-int (s/cat :head (s/* int?) :tail int?)
                 choice (s/alt :int int? :anything any?)
                 opts (s/keys* :req-un [:tests.spec-alpha/name]
                                :opt-un [:tests.spec-alpha/age])
                 explain-spec (s/cat :name string? :age int?)
                 problem (first (get (s/explain-data explain-spec ["Ada" "old"])
                                     problems-key))]
             {:and-conformer [(s/conform chained "ok")
                              (s/invalid? (s/conform chained 42))
                              (s/unform chained :ok)]
              :or-branch-order [(s/conform branch-order 1)
                                (s/conform branch-order -1)]
              :regex-backtracking [(s/conform greedy-tail [1 2 "done"])
                                   (s/conform greedy-last-int [1 2 3])
                                   (s/conform choice [1])]
              :keys-star-permutation [(s/conform opts [:age 42 :name "Ada"])
                                       (set (mapv vec
                                                  (partition 2
                                                             (s/unform opts
                                                                       {:name "Ada"
                                                                        :age 42}))))]
              :explain-path (select-keys problem [:path :in :val :via])}))
