;; Portable clojure.xml/basilisp.xml accepted-subset cases. The fixture
;; compares data trees rather than host parser objects. Clojure retains nil
;; :attrs/:content slots in its element struct maps; Basilisp omits empty keys,
;; so cases normalize both to explicit maps and vectors.

(require '[clojure.xml :as xml])

#?(:clj (import 'java.io.ByteArrayInputStream))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn parse-xml-text [source]
  #?(:clj (xml/parse (ByteArrayInputStream. (.getBytes source "UTF-8")))
     :lpy (xml/parse source)))

(defn normalize-element [element]
  {:tag (:tag element)
   :attrs (or (:attrs element) {})
   :content (mapv (fn [child]
                    (if (map? child)
                      (normalize-element child)
                      child))
                  (or (:content element) []))})

(defn parsed [source]
  (normalize-element (parse-xml-text source)))

(defn errors? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(emit-case :simple-and-attrs
           [(parsed "<root/>")
            (parsed "<root b=\"2\" a=\"1\"><child id=\"c1\"/></root>")])

(emit-case :mixed-content
           (parsed "<root>before<child>text</child>after<tail><leaf/>done</tail></root>"))

(emit-case :whitespace-comments-and-builtins
           {:whitespace (parsed "<root> \n\t<child/> <!-- omitted --> </root>")
            :builtins (parsed "<x a=\"&lt;&amp;&quot;&apos;\">&lt;&amp;&quot;&apos;</x>")})

(emit-case :malformed-input
           (mapv #(errors? (fn [] (parse-xml-text %)))
                 [""
                  "<x>"
                  "<x><y></x>"
                  "<1bad/>"]))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-element-corpus
           (loop [remaining 48
                  seed 578721382
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     s4 (next-seed s3)
                     label (str "n" (mod s1 100000))
                     attr (str "a" (mod s2 100000))
                     child (str "c" (mod s3 100000))
                     text (str "t" (mod s4 100000))
                     source (str "<" label " id=\"" attr "\">"
                                 text
                                 "<" child " value=\"" text "\"/>"
                                 "tail"
                                 "</" label ">")]
                 (recur (dec remaining)
                        s4
                        (conj result (parsed source)))))))
