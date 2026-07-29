;; Portable clojure.core namespace state, lookup, aliasing, referring, and
;; resolution semantics. All namespace mutations use fixture-private symbols and
;; are cleaned up so cases remain isolated when a failure interrupts execution.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(def lifecycle-ns 'core-namespace-state.lifecycle)
(def map-ns 'core-namespace-state.maps)
(def refer-target-ns 'core-namespace-state.refer-target)
(def refer-client-ns 'core-namespace-state.refer-client)
(def switched-ns 'core-namespace-state.switched)
(def evaled-ns 'core-namespace-state.evaled)
(def fuzz-ns 'core-namespace-state.fuzz)
(def missing-ns 'core-namespace-state.missing)

(def all-fixture-ns
  [lifecycle-ns
   map-ns
   refer-target-ns
   refer-client-ns
   switched-ns
   evaled-ns
   fuzz-ns
   missing-ns])

(defn cleanup! []
  (doseq [ns-sym all-fixture-ns]
    (when (find-ns ns-sym)
      (remove-ns ns-sym))))

(defn key-names [m]
  (sort (map str (keys m))))

(defn ns-sym [ns]
  (symbol (str (ns-name ns))))

(defn var-summary [v]
  (when v
    (let [m (meta v)]
      [(ns-sym (:ns m)) (:name m) (when (bound? v) @v)])))

(defn selected-var-summary [m ks]
  (into (sorted-map)
        (keep (fn [k]
                (when-let [v (get m k)]
                  [k (var-summary v)])))
        ks))

(cleanup!)

(emit-case :namespace-lifecycle-and-lookup
           (try
             (let [before (find-ns lifecycle-ns)
                   created (create-ns lifecycle-ns)
                   created-again (create-ns lifecycle-ns)
                   found (find-ns lifecycle-ns)
                   the-ns-checks [(= found (the-ns lifecycle-ns))
                                  (= found (the-ns found))
                                  (rejected? #(the-ns missing-ns))]
                   all-hit? (boolean
                             (some #(= lifecycle-ns (ns-sym %)) (all-ns)))
                   removed (remove-ns lifecycle-ns)
                   after (find-ns lifecycle-ns)]
               {:find-before (nil? before)
                :create [(ns-sym created)
                         (= created created-again)
                         (= created found)]
                :the-ns the-ns-checks
                :all-ns all-hit?
                :remove [(ns-sym removed)
                         (nil? after)
                         (nil? (remove-ns lifecycle-ns))]})
             (finally
               (cleanup!))))

(emit-case :namespace-maps-publics-and-unmap
           (try
             (let [n (create-ns map-ns)
                   public-var (intern n 'public-value 10)
                   private-var (intern n 'private-value 20)
                   declared-var (intern n 'declared-value)]
               (alter-meta! private-var assoc :private true)
               (let [before {:interns (key-names
                                       (select-keys (ns-interns n)
                                                    '[public-value
                                                      private-value
                                                      declared-value]))
                             :publics (key-names
                                       (select-keys (ns-publics n)
                                                    '[public-value
                                                      private-value
                                                      declared-value]))
                             :imports {:map? (map? (ns-imports n))
                                       :non-empty? (boolean (seq (ns-imports n)))}
                             :map-contains? [(contains? (ns-map n) 'public-value)
                                             (contains? (ns-map n) 'private-value)
                                             (contains? (ns-map n) 'declared-value)]
                             :resolve [(var-summary
                                        (ns-resolve n 'public-value))
                                       (nil? (ns-resolve n 'missing-value))]}]
                 {:before before
                  :unmap [(nil? (ns-unmap n 'public-value))
                          (nil? (get (ns-interns n) 'public-value))
                          (nil? (ns-resolve n 'public-value))]
                  :declared (var-summary declared-var)
                  :public-root @public-var}))
             (finally
               (cleanup!))))

(emit-case :namespace-alias-refer-and-resolve
           (try
             (let [target (create-ns refer-target-ns)
                   client (create-ns refer-client-ns)]
               (intern target 'keep 1)
               (intern target 'drop 2)
               (intern target 'old 3)
               (binding [*ns* client]
                 (alias 'rt refer-target-ns)
                 (refer refer-target-ns
                        :only '[keep old]
                        :rename '{old renamed})
                 (refer-clojure :only '[map])
                 (let [aliases (ns-aliases client)
                       refers (ns-refers client)
                       mapped (ns-map client)]
                   {:alias (ns-sym (get aliases 'rt))
                    :alias-keys (key-names (select-keys aliases '[rt]))
                    :refer-keys (key-names (select-keys refers
                                                        '[keep renamed drop map]))
                    :refer-vars (selected-var-summary refers '[keep renamed drop])
                    :resolve [(var-summary (ns-resolve client 'keep))
                              (var-summary (ns-resolve client 'renamed))
                              (boolean (ns-resolve client 'map))
                              (nil? (ns-resolve client 'drop))]
                    :map-contains? [(contains? mapped 'keep)
                                    (contains? mapped 'renamed)
                                    (contains? mapped 'map)
                                    (not (contains? mapped 'drop))]})))
             (finally
               (cleanup!))))

(emit-case :seeded-namespace-map-fuzz
           (try
             (let [n (create-ns fuzz-ns)
                   entries (mapv (fn [i]
                                   [(symbol (str "v" i)) (* i i)])
                                 (range 16))
                   syms (mapv first entries)
                   removed-syms (mapv #(symbol (str "v" %)) (range 0 16 3))]
               (doseq [[sym value] entries]
                 (let [v (intern n sym value)]
                   (when (odd? value)
                     (alter-meta! v assoc :private true))))
               (let [before {:interns (key-names (select-keys (ns-interns n) syms))
                             :publics (key-names (select-keys (ns-publics n) syms))
                             :resolved (mapv #(var-summary (ns-resolve n %)) syms)
                             :map-hits (mapv #(contains? (ns-map n) %) syms)}]
                 (doseq [sym removed-syms]
                   (ns-unmap n sym))
                 {:before before
                  :after {:interns (key-names (select-keys (ns-interns n) syms))
                          :publics (key-names (select-keys (ns-publics n) syms))
                          :removed? (mapv #(nil? (ns-resolve n %)) removed-syms)
                          :retained? (mapv #(boolean (ns-resolve n %))
                                           (remove (set removed-syms) syms))}}))
             (finally
               (cleanup!))))

(emit-case :namespace-switch-requiring-resolve-and-loaded-libs
           (try
             (let [original-ns *ns*
                   switched (try
                              (let [ret (in-ns switched-ns)]
                                [(ns-sym ret)
                                 (ns-sym *ns*)
                                 (boolean (find-ns switched-ns))])
                              (finally
                                (in-ns (symbol (str (ns-name original-ns))))))
                   resolved? (boolean
                              (requiring-resolve
                               #?(:clj 'clojure.string/blank?
                                  :lpy 'basilisp.string/blank?)))]
               {:in-ns switched
                :requiring-resolve [resolved?
                                    (nil?
                                     (requiring-resolve
                                      #?(:clj 'clojure.string/not-a-public
                                         :lpy 'basilisp.string/not-a-public)))
                                    (rejected? #(requiring-resolve 'plain-symbol))]
                :loaded-libs [(set? (loaded-libs))
                              (every? symbol? (loaded-libs))
                              (contains?
                               (loaded-libs)
                               #?(:clj 'clojure.string
                                  :lpy 'basilisp.string))]})
             (finally
               (cleanup!))))

(emit-case :eval-ns-macro-switches-current-namespace
           (try
             (let [original-ns *ns*
                   result (eval
                           (list 'ns evaled-ns
                                 (list :require
                                       '[clojure.string :as str])))
                   active-ns *ns*
                   aliases (ns-aliases active-ns)
                   summary {:result-nil? (nil? result)
                            :active      (ns-sym active-ns)
                            :found       (boolean (find-ns evaled-ns))
                            :loaded?     (contains? (loaded-libs) evaled-ns)
                            :alias?      (boolean (get aliases 'str))}]
               (in-ns (symbol (str (ns-name original-ns))))
               summary)
             (finally
               (cleanup!))))
