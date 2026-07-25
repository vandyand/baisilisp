;; Portable clojure.reflect/basilisp.reflect data-shape cases.

(require '[clojure.reflect :as r])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

#?(:lpy
   (def basilisp-extension-touch
     [r/->PythonReflector
      r/AsmReflector
      r/Constructor
      r/Field
      r/JavaReflector
      r/Method
      r/PythonReflector
      r/Reflectable
      r/reflect*])
   :clj
   (def basilisp-extension-touch nil))

(emit-case :reflect-public-surface
           (let [required '[->AsmReflector
                            ->Constructor
                            ->Field
                            ->JavaReflector
                            ->Method
                            ClassResolver
                            Reflector
                            TypeReference
                            do-reflect
                            flag-descriptors
                            map->Constructor
                            map->Field
                            map->Method
                            reflect
                            resolve-class
                            type-reflect
                            typename]]
             (every? #(contains? (ns-publics 'clojure.reflect) %) required)))

(emit-case :reflect-protocol-and-constructor-vars
           {:protocol-vars [(some? r/ClassResolver)
                            (some? r/Reflector)
                            (some? r/TypeReference)]
            :jvm-reflector-constructors [(some? (r/->JavaReflector nil))
                                         (some? (r/->AsmReflector (fn [_] nil)))]})

(emit-case :reflect-typename-symbols
           [(r/typename 'java.lang.String)
            (r/typename 'java.lang.String<>)
            (r/typename 'pkg/Name)])

(emit-case :reflect-record-constructors
           (let [method      (r/->Method 'run 'Object 'Demo ['String] ['Exception] #{:public})
                 field       (r/->Field 'value 'long 'Demo #{:private})
                 constructor (r/->Constructor 'Demo 'Demo ['String] [] #{:public})]
             [((juxt :name :return-type :declaring-class :parameter-types
                     :exception-types :flags)
               method)
              ((juxt :name :type :declaring-class :flags) field)
              ((juxt :name :declaring-class :parameter-types :exception-types :flags)
               constructor)]))

(emit-case :reflect-map-constructors
           [((juxt :name :return-type :declaring-class :parameter-types
                   :exception-types :flags)
             (r/map->Method {:name 'run}))
            ((juxt :name :type :declaring-class :flags)
             (r/map->Field {:name 'field}))
            ((juxt :name :declaring-class :parameter-types :exception-types :flags)
             (r/map->Constructor {:declaring-class 'Demo}))])

(emit-case :reflect-flag-descriptors
           [(count r/flag-descriptors)
            (first r/flag-descriptors)
            (last r/flag-descriptors)
            (set (mapcat :contexts r/flag-descriptors))])

(emit-case :reflect-protocol-functions
           {:typename [(r/typename 'java.lang.String)
                       (r/typename 'java.lang.String<>)
                       (r/typename 'pkg/Name)]
            :resolve-class (r/resolve-class (fn [name] [:resolved name]) 'Demo)
            :do-reflect (r/do-reflect
                         (reify r/Reflector
                           (do-reflect [_ typeref] {:typeref typeref}))
                         'Demo)})

(emit-case :reflect-entrypoints
           {:reflect-map? #?(:clj (map? (r/reflect String))
                             :lpy (map? (r/reflect python/str)))
            :type-reflect-map? #?(:clj (map? (r/type-reflect String))
                                  :lpy (map? (r/type-reflect python/str)))
            :reflect-nil #?(:clj true :lpy (nil? (r/reflect nil)))})
