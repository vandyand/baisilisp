;; Portable clojure.data.xml/basilisp.data.xml surface and semantic cases.
;; The fixture uses normalized values for XML trees/events so host classes and
;; serializer formatting do not create false mismatches.

(ns conformance.data-xml-cases
  (:require [clojure.string]
            [clojure.data.xml :as xml]
            [clojure.data.xml.event :as event]
            [clojure.data.xml.tree :as tree])
  #?(:clj (:import [java.io StringReader])))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn publics [ns-sym]
  (set (map name (keys (ns-publics ns-sym)))))

(def expected-xml-publics
  ["aggregate-xmlns" "alias-uri" "as-qname" "cdata" "element" "element*"
   "element-nss" "element?" "emit" "emit-str" "event-seq" "find-xmlns"
   "indent" "indent-str" "parse" "parse-qname" "parse-str"
   "print-uri-file-command!" "qname" "qname-local" "qname-uri"
   "sexp-as-element" "sexps-as-fragment" "symbol-uri" "uri-file"
   "uri-symbol" "xml-comment"])

(def expected-event-publics
  ["->CDataEvent" "->CharsEvent" "->CommentEvent" "->EmptyElementEvent"
   "->EndElementEvent" "->QNameEvent" "->StartElementEvent" "element-nss"
   "element-nss*" "end-element-event" "event-element" "event-exit?"
   "event-node" "map->CDataEvent" "map->CharsEvent" "map->CommentEvent"
   "map->EmptyElementEvent" "map->EndElementEvent" "map->QNameEvent"
   "map->StartElementEvent"])

(def expected-tree-publics
  ["event-tree" "flatten-elements" "seq-tree"])

(defn contains-all? [publics expected]
  (every? publics expected))

(defn normalize-newlines [s]
  (clojure.string/replace s #"\r\n" "\n"))

(defn qshape [name]
  [(xml/qname-uri name) (xml/qname-local name)])

(defn event-source [source]
  #?(:clj (StringReader. source)
     :lpy source))

(defn special-node-content [node]
  #?(:clj (try
            (.-content node)
            (catch Throwable _ ::not-special))
     :lpy (try
            (.-content node)
            (catch python/Exception _ ::not-special))))

(defn normalize-node [node]
  (cond
    (and (string? node) (re-matches #"\s+" node))
    :whitespace

    (xml/element? node)
    {:tag (qshape (:tag node))
     :attrs (into (sorted-map)
                  (map (fn [[k v]] [(qshape k) v]))
                  (:attrs node))
     :content (vec (remove #{:whitespace} (map normalize-node (:content node))))}

    (instance? #?(:clj clojure.data.xml.event.CDataEvent
                  :lpy event/CDataEvent)
               node)
    [:cdata-event (.-str node)]

    (instance? #?(:clj clojure.data.xml.event.CommentEvent
                  :lpy event/CommentEvent)
               node)
    [:comment-event (.-str node)]

    (not= ::not-special (special-node-content node))
    [:special (special-node-content node)]

    :else node))

(defn event-shape [event]
  (cond
    (instance? #?(:clj clojure.data.xml.event.StartElementEvent
                  :lpy event/StartElementEvent)
               event)
    [:start (qshape (.-tag event)) (into (sorted-map)
                                         (map (fn [[k v]] [(qshape k) v]))
                                         (.-attrs event))]

    (instance? #?(:clj clojure.data.xml.event.EmptyElementEvent
                  :lpy event/EmptyElementEvent)
               event)
    [:empty (qshape (.-tag event)) (into (sorted-map)
                                         (map (fn [[k v]] [(qshape k) v]))
                                         (.-attrs event))]

    (instance? #?(:clj clojure.data.xml.event.CharsEvent
                  :lpy event/CharsEvent)
               event)
    [:chars (.-str event)]

    (instance? #?(:clj clojure.data.xml.event.CDataEvent
                  :lpy event/CDataEvent)
               event)
    [:cdata (.-str event)]

    (instance? #?(:clj clojure.data.xml.event.CommentEvent
                  :lpy event/CommentEvent)
               event)
    [:comment (.-str event)]

    (instance? #?(:clj clojure.data.xml.event.QNameEvent
                  :lpy event/QNameEvent)
               event)
    [:qname (qshape (.-qn event))]

    (event/event-exit? event)
    [:end (some-> (.-tag event) qshape)]

    :else [:unknown (str event)]))

(emit-case :public-surfaces
           {:xml (contains-all? (publics #?(:clj 'clojure.data.xml
                                            :lpy 'basilisp.data.xml))
                                expected-xml-publics)
            :event (contains-all? (publics #?(:clj 'clojure.data.xml.event
                                              :lpy 'basilisp.data.xml.event))
                                  expected-event-publics)
            :tree (contains-all? (publics #?(:clj 'clojure.data.xml.tree
                                             :lpy 'basilisp.data.xml.tree))
                                 expected-tree-publics)})

(emit-case :direct-public-var-smoke
           {:xml (every? some?
                         [xml/aggregate-xmlns
                          xml/alias-uri
                          xml/as-qname
                          xml/cdata
                          xml/element
                          xml/element*
                          xml/element-nss
                          xml/element?
                          xml/emit
                          xml/emit-str
                          xml/event-seq
                          xml/find-xmlns
                          xml/indent
                          xml/indent-str
                          xml/parse
                          xml/parse-qname
                          xml/parse-str
                          xml/print-uri-file-command!
                          xml/qname
                          xml/qname-local
                          xml/qname-uri
                          xml/sexp-as-element
                          xml/sexps-as-fragment
                          xml/symbol-uri
                          xml/uri-file
                          xml/uri-symbol
                          xml/xml-comment])
            :event (every? some?
                           [event/->CDataEvent
                            event/->CharsEvent
                            event/->CommentEvent
                            event/->EmptyElementEvent
                            event/->EndElementEvent
                            event/->QNameEvent
                            event/->StartElementEvent
                            event/element-nss
                            event/element-nss*
                            event/end-element-event
                            event/event-element
                            event/event-exit?
                            event/event-node
                            event/map->CDataEvent
                            event/map->CharsEvent
                            event/map->CommentEvent
                            event/map->EmptyElementEvent
                            event/map->EndElementEvent
                            event/map->QNameEvent
                            event/map->StartElementEvent])
            :tree (every? some?
                          [tree/event-tree
                           tree/flatten-elements
                           tree/seq-tree])})

(emit-case :direct-basilisp-extension-var-smoke
           {:xml #?(:clj true
                    :lpy (every? some?
                                 [xml/->CDataEvent
                                  xml/->CharsEvent
                                  xml/->CommentEvent
                                  xml/->EmptyElementEvent
                                  xml/->EndElementEvent
                                  xml/->QNameEvent
                                  xml/->StartElementEvent
                                  xml/CDataEvent
                                  xml/CharsEvent
                                  xml/CommentEvent
                                  xml/EmptyElementEvent
                                  xml/EndElementEvent
                                  xml/QNameEvent
                                  xml/StartElementEvent
                                  xml/decode-uri
                                  xml/element-nss*
                                  xml/encode-uri
                                  xml/end-element-event
                                  xml/event-element
                                  xml/event-exit?
                                  xml/event-node
                                  xml/event-tree
                                  xml/flatten-elements
                                  xml/map->Element
                                  xml/namespaced?
                                  xml/tagged-element]))
            :event #?(:clj true
                      :lpy (every? some?
                                   [event/CDataEvent
                                    event/CharsEvent
                                    event/CommentEvent
                                    event/EmptyElementEvent
                                    event/EndElementEvent
                                    event/QNameEvent
                                    event/StartElementEvent]))})

(emit-case :qname-uri-helpers
           (let [space-uri "urn space"
                 dav "DAV:"
                 parsed (xml/parse-qname "{urn:x}book")]
             {:uri-symbol [(str (xml/uri-symbol dav))
                           (xml/symbol-uri (xml/uri-symbol dav))
                           (xml/uri-file dav)]
              :space-uri [(str (xml/uri-symbol space-uri))
                          (xml/symbol-uri (xml/uri-symbol space-uri))
                          (xml/uri-file space-uri)]
              :parsed [(qshape parsed)
                       (qshape "{urn:x}book")
                       (qshape (xml/qname "urn:x" "book"))
                       (qshape (xml/as-qname "{urn:x}book"))]
              :print-command (normalize-newlines
                              (with-out-str
                                (xml/print-uri-file-command! dav)))
              :alias (do
                       (xml/alias-uri :D dav)
                       (str (ns-name (get (ns-aliases *ns*) 'D))))}))

(emit-case :element-metadata-and-nss
           (let [el (xml/element* :root nil [nil "x"] {:m true})
                 raw-el (xml/element* :root nil [] {:clojure.data.xml/nss {"q" "urn:q"}})
                 nss-el (xml/element* :root
                                      {:xmlns/p "urn:p"
                                       (xml/qname "urn:a" "id") "7"}
                                      [])
                 nss (xml/element-nss nss-el)
                 raw (event/element-nss* raw-el)
                 aggregate (xml/aggregate-xmlns
                            (xml/element :root nil
                                         (xml/element (xml/qname "urn:child" "node")
                                                      {(xml/qname "urn:attr" "id") "1"})))]
             {:element (normalize-node el)
              :meta (meta el)
              :raw-nss raw
              :nss-p (get-in nss [:p->u "p"])
              :nss-q (get-in nss [:p->u "q"])
              :nss-attr-uri? (contains? (set (keys (:u->ps nss))) "urn:a")
              :find-xmlns (sort (xml/find-xmlns nss-el))
              :aggregate-uris (sort (keys (:u->ps (event/element-nss* aggregate))))}))

(emit-case :event-constructors-and-tree-roundtrip
           (let [start (event/map->StartElementEvent {:tag :root
                                                      :attrs {:a "1"}
                                                      :nss {}
                                                      :location-info nil})
                 empty (event/map->EmptyElementEvent {:tag :empty
                                                      :attrs {}
                                                      :nss {}
                                                      :location-info nil})
                 chars (event/map->CharsEvent {:str "x"})
                 cdata (event/map->CDataEvent {:str "y < z"})
                 comment (event/map->CommentEvent {:str " note "})
                 qn (event/map->QNameEvent {:qn :name})
                 end (event/map->EndElementEvent {:tag :root
                                                  :nss {}
                                                  :location-info nil})
                 tree (xml/element :root {:a "1"}
                                   "x"
                                   (xml/cdata "y < z")
                                   (xml/xml-comment " note ")
                                   (xml/element :empty))]
             {:constructors (mapv event-shape
                                  [start empty chars cdata comment qn end])
              :event-node [(event/event-node chars)
                           (normalize-node (event/event-node cdata))
                           (normalize-node (event/event-node comment))]
              :event-element (normalize-node (event/event-element start ["body"]))
              :flattened (mapv event-shape (tree/flatten-elements [tree]))
              :roundtrip (normalize-node (tree/event-tree (tree/flatten-elements [tree])))}))

(emit-case :parse-emit-boundaries
           (let [source "<root xmlns='urn:r' xmlns:a='urn:a' a:id='7'>x<child><![CDATA[y < z]]></child><!-- note --></root>"
                 parsed (xml/parse-str source :include-node? #{:element :characters :comment})
                 emitted (xml/emit-str parsed :declaration false)
                 indented (xml/indent-str parsed :declaration false)]
             {:parsed (normalize-node parsed)
              :emitted-roundtrip (normalize-node (xml/parse-str emitted
                                                                :include-node? #{:element :characters :comment}))
              :indented-roundtrip (normalize-node (xml/parse-str indented
                                                                 :include-node? #{:element :characters :comment}))
              :events (mapv event-shape (xml/event-seq (event-source source)
                                                       {:include-node? #{:element :characters :comment}}))}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-tree-roundtrip-corpus
           (loop [remaining 48
                  seed 871263
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     uri (str "urn:seed:" (mod s1 11))
                     attr-uri (str "urn:attr:" (mod s2 7))
                     value (str "v" (mod s3 997))
                     tree (xml/element (xml/qname uri "root")
                                       {(xml/qname attr-uri "id") value}
                                       value
                                       (xml/element :child nil
                                                    (xml/cdata (str "c<" value))))]
                 (recur (dec remaining)
                        s3
                        (conj result
                              {:same-after-emit? (= (normalize-node tree)
                                                    (normalize-node
                                                     (xml/parse-str
                                                      (xml/emit-str tree
                                                                    :declaration false))))
                               :same-after-events? (= (normalize-node tree)
                                                     (normalize-node
                                                      (tree/event-tree
                                                       (tree/flatten-elements [tree]))))
                               :xmlns (sort
                                       (xml/find-xmlns
                                        (xml/element (xml/qname uri "root")
                                                     {(xml/qname attr-uri "id") value})))}))))))
