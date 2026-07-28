;; Portable clojure.core-deftype public behavior hardening. The bundled
;; clojure.core-deftype source is not a requireable namespace, so these cases
;; verify its observable public surface through defrecord/deftype/reify.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defrecord NilEntryRecord [a b])

(defprotocol DeftypeFixtureProtocol
  (fixture-method [this x]))

(deftype ProtocolType [label]
  DeftypeFixtureProtocol
  (fixture-method [this x]
    [label x]))

(defn normalize-entry [entry]
  (when entry
    [(first entry) (second entry)]))

(emit-case :record-nil-entry-contracts
           (let [base (->NilEntryRecord nil 2)
                 extra (assoc base :extra nil)
                 from-map (map->NilEntryRecord {:a nil :b nil :extra nil})]
             {:field-entry [(contains? base :a)
                            (nil? (:a base))
                            (normalize-entry (find base :a))
                            (contains? base :missing)
                            (normalize-entry (find base :missing))]
              :extra-entry [(contains? extra :extra)
                            (nil? (:extra extra))
                            (normalize-entry (find extra :extra))]
              :map-constructor [(contains? from-map :a)
                                (contains? from-map :b)
                                (contains? from-map :extra)
                                (normalize-entry (find from-map :a))
                                (normalize-entry (find from-map :b))
                                (normalize-entry (find from-map :extra))]
              :seq-contains-nil-entries (set (map normalize-entry
                                                  (seq from-map)))}))

(emit-case :record-nil-entry-update-fuzz
           (mapv (fn [n]
                   (let [r0 (->NilEntryRecord n nil)
                         r1 (assoc r0
                                   :a (when (odd? n) n)
                                   :extra (when (zero? (mod n 3)) n)
                                   :nil-extra nil)
                         r2 (if (zero? (mod n 4))
                              (dissoc r1 :a)
                              r1)]
                     {:n n
                      :record? (record? r2)
                      :contains [(contains? r2 :a)
                                 (contains? r2 :b)
                                 (contains? r2 :extra)
                                 (contains? r2 :nil-extra)]
                      :entries (mapv (fn [k]
                                       [k (normalize-entry (find r2 k))])
                                     [:a :b :extra :nil-extra])
                      :as-map (into (sorted-map) r2)}))
                 (range 16)))

(emit-case :deftype-and-reify-protocol-contracts
           {:deftype [(instance? ProtocolType (->ProtocolType :type))
                      (fixture-method (->ProtocolType :type) :x)
                      (not (record? (->ProtocolType :type)))]
            :reify (let [closed :closed
                         obj (reify
                               DeftypeFixtureProtocol
                               (fixture-method [this x]
                                 [closed x]))]
                     [(satisfies? DeftypeFixtureProtocol obj)
                      (fixture-method obj :y)
                      (not (record? obj))])})
