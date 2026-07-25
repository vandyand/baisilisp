;; Portable clojure.core collection/array/transient residual helper semantics.
;; Host arrays and XML nodes are normalized into vectors and tag names so the
;; fixture compares behavior rather than host object identity.

(require '[clojure.xml :as xml])

#?(:clj (import 'java.io.ByteArrayInputStream)
   :lpy (import [xml.etree.ElementTree :as etree]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn array-2d-summary [value]
  (mapv vec value))

(defn parse-xml-root [source]
  #?(:clj (xml/parse (ByteArrayInputStream. (.getBytes source "UTF-8")))
     :lpy (etree/fromstring source)))

(defn xml-tag [node]
  #?(:clj (:tag node)
     :lpy (.-tag node)))

(defn xml-tag-name [node]
  (let [tag (xml-tag node)]
    (if (keyword? tag) (name tag) (str tag))))

(emit-case :array-conversion-boundaries
           {:to-array [(vec (to-array nil))
                       (vec (to-array []))
                       (vec (to-array '(1 nil :a)))
                       (vec (to-array (sorted-set 3 1 2)))]
            :to-array-2d [(rejected? #(to-array-2d nil))
                          (array-2d-summary (to-array-2d []))
                          (array-2d-summary (to-array-2d [[1 2] nil [3]]))
                          (array-2d-summary (to-array-2d '((:a :b) () nil)))]})

(emit-case :collection-reversal-and-removal
           {:disj [(disj nil :a)
                   (disj #{:a :b :c} :a :missing)
                   (disj #{:a :b :c} :a :b :c :d)
                   (disj (sorted-set 3 1 2) 2 4)]
            :rseq [(vec (rseq [:a :b :c]))
                   (mapv vec (rseq (sorted-map :a 1 :b 2 :c 3)))
                   (rejected? #(rseq nil))
                   (rejected? #(rseq '(:a :b)))]})

(emit-case :transient-mutator-boundaries
           {:conj [(persistent! (conj!))
                   (persistent! (conj! (transient []) :a))
                   (persistent! (conj! (transient #{:a}) :b))
                   (persistent! (conj! (transient {}) [:a 1]))
                   (rejected? #(conj! (transient []) :a :b))]
            :disj [(persistent! (disj! (transient #{:a :b :c}) :a :x))
                   (persistent! (disj! (disj! (transient #{:a :b :c}) :b)
                                       :c))]
            :dissoc [(persistent! (dissoc! (transient {:a 1 :b 2 :c 3})
                                           :a
                                           :x))
                     (persistent! (dissoc! (dissoc! (transient {:a 1 :b 2})
                                                     :b)
                                           :a))]
            :pop [(persistent! (pop! (transient [:a :b :c])))
                  (persistent! (pop! (pop! (transient [:a :b]))))
                  (rejected? #(pop! (transient [])))]})

(emit-case :vector-of-coercion-and-rejection
           {:values {:boolean (vector-of :boolean true false 1 nil)
                     :byte (vector-of :byte -128 0 127)
                     :char (vector-of :char \a \b)
                     :short (vector-of :short -32768 32767)
                     :int (vector-of :int 1.9 -2147483648 2147483647)
                     :long (vector-of :long 1.9)
                     :float (mapv double (vector-of :float 16777217))
                     :double (vector-of :double 1 2.5)}
            :rejections [(rejected? #(vector-of :object 1))
                         (rejected? #(vector-of :byte 128))
                         (rejected? #(vector-of :short 32768))
                         (rejected? #(vector-of :int 2147483648))
                         (rejected? #(vector-of :char "a"))]})

(emit-case :xml-seq-depth-first-tags
           (let [root (parse-xml-root "<root><a/><b><c/><d/></b><e/></root>")]
             (mapv xml-tag-name (xml-seq root))))

(emit-case :seeded-transient-and-array-fuzz
           (mapv (fn [n]
                   (let [xs (mapv #(+ n %) (range 5))
                         remove-xs (take 3 xs)
                         arr (to-array xs)
                         arr2 (to-array-2d [xs nil (reverse xs)])
                         tv (reduce conj! (transient []) xs)
                         ts (reduce disj! (transient (set xs)) remove-xs)
                         tm (reduce dissoc!
                                    (transient (zipmap xs (map #(* % %) xs)))
                                    remove-xs)]
                     {:n n
                      :array (vec arr)
                      :array-2d (array-2d-summary arr2)
                      :vector (persistent! tv)
                      :set (sort (persistent! ts))
                      :map (into (sorted-map) (persistent! tm))}))
                 (range -4 5)))
