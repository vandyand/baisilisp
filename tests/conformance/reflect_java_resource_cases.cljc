;; clojure.reflect.java source-resource hardening.
;;
;; The upstream clojure/reflect/java.clj file is loaded into clojure.reflect
;; with in-ns and is not a separate portable public namespace. These cases pin
;; the public data/protocol contracts it exposes through clojure.reflect.

(require '[clojure.reflect :as r])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn member-summary [member]
  (cond
    (contains? member :return-type)
    [:method (:name member) (:return-type member) (:declaring-class member)
     (:parameter-types member) (:exception-types member) (:flags member)]

    (contains? member :type)
    [:field (:name member) (:type member) (:declaring-class member)
     (:flags member)]

    :else
    [:constructor (:name member) (:declaring-class member)
     (:parameter-types member) (:exception-types member) (:flags member)]))

(def seeded-symbols
  ['java.lang.String
   'java.lang.String<>
   'java.util.Map$Entry
   'pkg/Outer$Inner
   'pkg/Name
   'demo/run
   'with-dash
   'UPPER
   '_hidden])

(def seeded-flags
  [#{}
   #{:public}
   #{:private :static}
   #{:protected :final}
   #{:public :static :final :synthetic}])

(emit-case :reflect-java-resource-require-after-reflect
           (nil? (require 'clojure.reflect.java)))

(emit-case :reflect-java-flag-table-exact
           r/flag-descriptors)

(emit-case :reflect-java-record-map-contracts
           (let [method      (r/->Method 'm 'Ret 'Owner ['A 'B] ['E] #{:public})
                 field       (r/->Field 'f 'FieldType 'Owner #{:private})
                 constructor (r/->Constructor 'Owner 'Owner ['A] [] #{:public})]
             {:summaries [(member-summary method)
                          (member-summary field)
                          (member-summary constructor)]
              :keys [(vec (keys method))
                     (vec (keys field))
                     (vec (keys constructor))]
              :contains-nil [(contains? (r/map->Method {:name 'm}) :return-type)
                             (contains? (r/map->Field {:name 'f}) :type)
                             (contains? (r/map->Constructor {:name 'Owner})
                                        :parameter-types)]
              :assoc-extra [(get (assoc method :extra 1) :extra)
                            (:name (dissoc (assoc field :extra 1) :extra))
                            (count (seq constructor))]}))

(emit-case :reflect-java-record-seeded-members
           (mapv (fn [n]
                   (let [a     (nth seeded-symbols (mod n (count seeded-symbols)))
                         b     (nth seeded-symbols (mod (+ n 2) (count seeded-symbols)))
                         c     (nth seeded-symbols (mod (+ n 4) (count seeded-symbols)))
                         flags (nth seeded-flags (mod n (count seeded-flags)))
                         params (vec (take (mod n 5) (cycle seeded-symbols)))
                         exceptions (vec (take (mod n 3)
                                               (cycle (reverse seeded-symbols))))]
                     [n
                      (member-summary (r/->Method a b c params exceptions flags))
                      (member-summary (r/->Field a b c flags))
                      (member-summary (r/->Constructor c c params exceptions flags))]))
                 (range 48)))

(emit-case :reflect-java-protocol-shells
           {:resolver-fn (r/resolve-class (fn [name] [:resolved name]) 'Demo)
            :custom-reflector (r/do-reflect
                               (reify r/Reflector
                                 (do-reflect [_ typeref]
                                   {:typeref typeref
                                    :typename (r/typename typeref)}))
                               'java.lang.String<>)
            :jvm-shells [(satisfies? r/Reflector (r/->JavaReflector nil))
                         (satisfies? r/Reflector
                                     (r/->AsmReflector (fn [_] nil)))]})

(emit-case :reflect-java-host-boundary
           #?(:clj
              {:java-host-boundary-observed?
               (or (map? (r/do-reflect (r/->JavaReflector nil) String))
                   (rejected? #(r/do-reflect (r/->JavaReflector nil) String)))
               :asm-host-boundary-observed?
               (or (rejected?
                    #(r/do-reflect
                      (r/->AsmReflector
                       (fn [typeref]
                         (.getResourceAsStream
                          (.getContextClassLoader (Thread/currentThread))
                          (str (.replace (r/typename typeref) "." "/")
                               ".class"))))
                      String))
                   (map? (r/do-reflect
                          (r/->AsmReflector
                           (fn [typeref]
                             (.getResourceAsStream
                              (.getContextClassLoader (Thread/currentThread))
                              (str (.replace (r/typename typeref) "." "/")
                                   ".class"))))
                          String)))}
              :lpy
              {:java-host-boundary-observed?
               (rejected? #(r/do-reflect (r/->JavaReflector nil)
                                          'java.lang.String))
               :asm-host-boundary-observed?
               (rejected? #(r/do-reflect
                             (r/->AsmReflector (fn [_] nil))
                             'java.lang.String))}))
