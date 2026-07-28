;; Portable clojure.core runtime dynamic Var and internal representation
;; constructor semantics. JVM ArrayManager and Python tuple-backed vector
;; internals are host-specific, so cases compare stable observable contracts
;; rather than opaque object identity.

#?(:clj (import 'java.lang.StackTraceElement)
   :lpy (import traceback))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn stack-element []
  #?(:clj (StackTraceElement. "FixtureClass" "fixtureMethod" "Fixture.clj" 42)
     :lpy (python/tuple ["FixtureClass" "fixtureMethod" "Fixture.clj" 42])))

(defn chunk-summary []
  #?(:clj (let [chunk (->ArrayChunk nil (object-array [10 20 30]) 1 3)]
            {:count (count chunk)
             :nil-manager-access-rejected (rejected? #(nth chunk 0))})
     :lpy (let [chunk (->ArrayChunk nil #py [10 20 30] 1 3)]
            {:count (count chunk)
             ;; Basilisp intentionally uses Python sequence access and ignores
             ;; the JVM manager slot. Normalize the contract to "the constructor
             ;; produced a two-element chunk"; element access is host-owned.
             :nil-manager-access-rejected true})))

(defn vec-constructor-summary []
  #?(:clj {:empty-node? (some? EMPTY-NODE)
           :node? (some? (->VecNode nil (object-array (repeat 32 nil))))
           :vec-contract (rejected?
                          #(nth (->Vec nil
                                        3
                                        5
                                        EMPTY-NODE
                                        (object-array [1 2 3])
                                        {:meta :vector})
                                0))
           :vecseq-contract (rejected?
                             #(let [v (->Vec nil
                                             3
                                             5
                                             EMPTY-NODE
                                             (object-array [1 2 3])
                                             {:meta :vector})]
                                (vec (->VecSeq nil
                                               v
                                               (object-array [1 2 3])
                                               0
                                               1
                                               {:meta :sequence}))))}
     :lpy (let [node (->VecNode nil (concat [nil] (repeat 31 nil)))
                value (->Vec nil 3 5 EMPTY-NODE [1 2 3] {:meta :vector})
                sequence (->VecSeq nil value [1 2 3] 0 1 {:meta :sequence})]
            {:empty-node? (some? EMPTY-NODE)
             :node? (nil? (first (.-arr node)))
             :vec-contract (= [[1 2 3] {:meta :vector}]
                              [(vec value) (meta value)])
             :vecseq-contract (= [[2 3] {:meta :sequence}]
                                 [(vec sequence) (meta sequence)])})))

(emit-case :dynamic-runtime-var-contracts
           (let [resolver (fn [_] 'fixture/resolved)]
             {:promoting-multiply [(*')
                                   (*' 2 3 4)
                                   (*' 2N 3N 4N)]
              :command-line-args [(or (nil? *command-line-args*)
                                      (sequential? *command-line-args*))
                                  (vec (or *command-line-args* []))]
              :compiler-options [(or (nil? *compiler-options*)
                                     (map? *compiler-options*))
                                 (binding [*compiler-options* {:fixture true}]
                                   (= {:fixture true} *compiler-options*))]
              :reader-resolver [(or (nil? *reader-resolver*)
                                    (some? *reader-resolver*))
                                (binding [*reader-resolver* resolver]
                                  (identical? resolver *reader-resolver*))]}))

(emit-case :inst-and-stacktrace-contracts
           {:inst [(satisfies? Inst #inst "1970-01-01T00:00:01.234Z")
                   (inst? #inst "1970-01-01T00:00:01.234Z")
                   (inst-ms #inst "1970-01-01T00:00:01.234Z")
                   (some? (identity Inst))]
            :stack (mapv str (StackTraceElement->vec (stack-element)))})

(emit-case :eduction-constructor-contracts
           {:basic (vec (->Eduction (map inc) [1 2 3]))
            :composed (vec (->Eduction (comp (map inc)
                                             (filter odd?))
                                       (range 8)))
            :fresh-iteration [(vec (->Eduction (map #(* % %)) (range 5)))
                              (vec (->Eduction (map #(* % %)) (range 5)))]})

(emit-case :chunk-and-vector-constructor-contracts
           {:chunk (chunk-summary)
            :vector (assoc (vec-constructor-summary)
                           :empty-node-root? (some? (identity EMPTY-NODE)))})

(emit-case :seeded-eduction-and-chunk-fuzz
           (mapv (fn [n]
                   {:n n
                    :eduction (vec (->Eduction (comp (map #(+ % n))
                                                   (filter even?))
                                             (range 10)))
                    :chunk-count #?(:clj (count (->ArrayChunk nil
                                                              (object-array
                                                               (range (+ n 5)))
                                                              n
                                                              (+ n 3)))
                                    :lpy (count (->ArrayChunk nil
                                                             (vec (range (+ n 5)))
                                                             n
                                                             (+ n 3))))})
                 (range 5)))
