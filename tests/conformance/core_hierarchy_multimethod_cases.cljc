;; Portable clojure.core hierarchy and multimethod helper semantics. Host class
;; names are normalized away; hierarchy and dispatch values use qualified
;; keywords so Clojure and Basilisp can compare exact EDN results.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn sorted-set-values [s]
  (vec (sort (or s #{}))))

(defn sorted-map-set-values [m]
  (into (sorted-map)
        (map (fn [[k v]] [k (sorted-set-values v)]) m)))

(defn method-keys [mf]
  (vec (sort (keys (methods mf)))))

(emit-case :hierarchy-transitive-underive-and-class-shape
           (let [h0 (make-hierarchy)
                 h1 (-> h0
                        (derive :hm/square :hm/rectangle)
                        (derive :hm/rectangle :hm/quadrilateral)
                        (derive :hm/quadrilateral :hm/polygon)
                        (derive :hm/triangle :hm/polygon)
                        (derive :hm/square :hm/regular)
                        (derive :hm/red-square :hm/square))
                 h2 (underive h1 :hm/rectangle :hm/quadrilateral)
                 host-class #?(:clj java.util.ArrayList
                               :lpy python/list)
                 root-class #?(:clj Object
                              :lpy python/object)
                 h-class (derive h0 root-class :hm/root-host)]
             {:initial-empty [(parents h0 :hm/missing)
                              (ancestors h0 :hm/missing)
                              (descendants h0 :hm/missing)]
              :parents [(sorted-set-values (parents h1 :hm/square))
                        (sorted-set-values (parents h1 :hm/red-square))]
              :ancestors [(sorted-set-values (ancestors h1 :hm/red-square))
                          (sorted-set-values (ancestors h1 :hm/square))]
              :descendants [(sorted-set-values (descendants h1 :hm/polygon))
                            (sorted-set-values (descendants h1 :hm/rectangle))]
              :isa [(isa? h1 :hm/red-square :hm/polygon)
                    (isa? h1 :hm/red-square :hm/regular)
                    (isa? h1 [:hm/red-square :hm/regular]
                          [:hm/rectangle :hm/regular])
                    (isa? h1 :hm/triangle :hm/regular)]
              :underive [(isa? h2 :hm/square :hm/polygon)
                         (isa? h2 :hm/red-square :hm/polygon)
                         (isa? h2 :hm/square :hm/regular)
                         (sorted-set-values (parents h2 :hm/rectangle))
                         (sorted-set-values (descendants h2 :hm/polygon))]
              :invalid [(rejected? #(derive h1 :hm/polygon :hm/red-square))
                        (rejected? #(derive h1 :hm/square :hm/square))
                        (rejected? #(derive {} :hm/a :hm/b))]
              :nil-type (type nil)
              :class-shape [(boolean (seq (bases host-class)))
                             (boolean (seq (supers host-class)))
                             (boolean (seq (bases root-class)))
                             (boolean (seq (supers root-class)))]
              :class-derived-root [(isa? h-class host-class root-class)
                                   (isa? h-class host-class :hm/root-host)
                                   (sorted-set-values (parents h-class root-class))
                                   (contains? (ancestors h-class host-class)
                                              :hm/root-host)]}))

(def ^:dynamic hm-dispatch-hierarchy
  (-> (make-hierarchy)
      (derive :hm/dog :hm/pet)
      (derive :hm/dog :hm/canid)
      (derive :hm/wolf :hm/canid)))

(defmulti hm-kind
  :kind
  :default :hm/default
  :hierarchy #'hm-dispatch-hierarchy)

(defmethod hm-kind :hm/pet [m]
  [:pet (:name m)])

(defmethod hm-kind :hm/canid [m]
  [:canid (:name m)])

(defmethod hm-kind :hm/default [m]
  [:default (:kind m)])

(emit-case :multimethod-preference-removal-and-defaults
           (let [dog {:kind :hm/dog :name "fido"}
                 wolf {:kind :hm/wolf :name "akela"}
                 lizard {:kind :hm/lizard :name "liz"}
                 ambiguous? (rejected? #(hm-kind dog))
                 prefer-ret (prefer-method hm-kind :hm/pet :hm/canid)
                 pet-method (get-method hm-kind :hm/pet)
                 dog-method (get-method hm-kind :hm/dog)
                 before-remove (method-keys hm-kind)
                 preferred (hm-kind dog)
                 wolf-result (hm-kind wolf)
                 default-result (hm-kind lizard)
                 remove-ret (remove-method hm-kind :hm/pet)
                 after-remove-keys (method-keys hm-kind)
                 after-remove-dog (hm-kind dog)
                 missing-remove-ret (remove-method hm-kind :hm/missing)
                 remove-all-ret (remove-all-methods hm-kind)]
             {:ambiguous? ambiguous?
              :prefer-return-same? (identical? prefer-ret hm-kind)
              :prefers (sorted-map-set-values (prefers hm-kind))
              :methods-before before-remove
              :get-method [(boolean pet-method)
                           (boolean dog-method)
                           (pet-method {:kind :hm/pet :name "spot"})
                           (dog-method dog)]
              :dispatch [preferred wolf-result default-result]
              :remove-method-return-same? (identical? remove-ret hm-kind)
              :after-remove [after-remove-keys after-remove-dog]
              :missing-remove-return-same? (identical? missing-remove-ret hm-kind)
              :remove-all-return-same? (identical? remove-all-ret hm-kind)
              :after-remove-all [(method-keys hm-kind)
                                 (rejected? #(hm-kind dog))
                                 (boolean (get-method hm-kind :hm/default))]}))

(def ^:private hm-number-type #?(:clj java.lang.Number :lpy :hm/number))
#?(:lpy (derive python/int hm-number-type))

(defmulti hm-self-recursive
  (fn
    ([] :hm/nil)
    ([x] (type x))
    ([x y] [(type x) (type y)])
    ([x y & _] :hm/nary)))

(defmethod hm-self-recursive :hm/nil []
  0)

(defmethod hm-self-recursive hm-number-type [x]
  x)

(defmethod hm-self-recursive [hm-number-type hm-number-type] [x y]
  (+ x y))

(defmethod hm-self-recursive :hm/nary
  [x y & more]
  (if more
    (recur (hm-self-recursive x y) (first more) (next more))
    (hm-self-recursive x y)))

(emit-case :multimethod-self-recursive-var-dispatch
           {:nulary (hm-self-recursive)
            :unary (hm-self-recursive 7)
            :binary (hm-self-recursive 3 4)
            :nary (hm-self-recursive 1 2 3 4)
            :method-selected (boolean
                              (get-method hm-self-recursive
                                          [#?(:clj java.lang.Long :lpy python/int)
                                           #?(:clj java.lang.Long :lpy python/int)]))})

(emit-case :seeded-hierarchy-fuzz
           (mapv (fn [[child parent grandparent]]
                   (let [h (-> (make-hierarchy)
                               (derive child parent)
                               (derive parent grandparent))
                         h' (underive h parent grandparent)]
                     {:edge [child parent grandparent]
                      :parents (sorted-set-values (parents h child))
                      :ancestors (sorted-set-values (ancestors h child))
                      :descendants (sorted-set-values (descendants h grandparent))
                      :before [(isa? h child grandparent)
                               (isa? h child parent)]
                      :after [(isa? h' child grandparent)
                              (isa? h' child parent)
                              (sorted-set-values (ancestors h' child))]}))
                 [[:hm/seed-a :hm/seed-b :hm/seed-c]
                  [:hm/seed-d :hm/seed-e :hm/seed-f]
                  [:hm/seed-g :hm/seed-h :hm/seed-i]]))
