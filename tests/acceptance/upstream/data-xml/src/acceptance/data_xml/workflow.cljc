(ns acceptance.data-xml.workflow
  (:require [clojure.string :as str]
            [clojure.data.xml :as xml]
            [clojure.data.xml.event :as event]
            [clojure.data.xml.tree :as tree])
  #?(:clj (:import [java.io StringReader StringWriter])
     :lpy (:import io)))

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

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn publics [ns-sym]
  (set (map name (keys (ns-publics ns-sym)))))

(defn contains-all? [actual expected]
  (every? actual expected))

(defn public-summary []
  {:xml (contains-all? (publics 'clojure.data.xml) expected-xml-publics)
   :event (contains-all? (publics 'clojure.data.xml.event) expected-event-publics)
   :tree (contains-all? (publics 'clojure.data.xml.tree) expected-tree-publics)})

(defn normalize-newlines [s]
  (str/replace s #"\r\n" "\n"))

(defn qshape [name]
  [(xml/qname-uri name) (xml/qname-local name)])

(defn event-source [source]
  #?(:clj (StringReader. source)
     :lpy source))

(defn string-writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-string [writer]
  #?(:clj (str writer)
     :lpy (.getvalue writer)))

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

(defn qname-summary []
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

(defn element-summary []
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

(defn event-summary []
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
    {:constructors (mapv event-shape [start empty chars cdata comment qn end])
     :event-node [(event/event-node chars)
                  (normalize-node (event/event-node cdata))
                  (normalize-node (event/event-node comment))]
     :event-element (normalize-node (event/event-element start ["body"]))
     :flattened (mapv event-shape (tree/flatten-elements [tree]))
     :roundtrip (normalize-node (tree/event-tree (tree/flatten-elements [tree])))}))

(defn parse-emit-summary []
  (let [source "<root xmlns='urn:r' xmlns:a='urn:a' a:id='7'>x<child><![CDATA[y < z]]></child><!-- note --></root>"
        parsed (xml/parse-str source :include-node? #{:element :characters :comment})
        emitted (xml/emit-str parsed :declaration false)
        indented (xml/indent-str parsed :declaration false)
        writer (string-writer)]
    (xml/emit parsed writer :declaration false)
    {:parsed (normalize-node parsed)
     :emit-writer-roundtrip (normalize-node (xml/parse-str (writer-string writer)
                                                           :include-node? #{:element :characters :comment}))
     :emitted-roundtrip (normalize-node (xml/parse-str emitted
                                                       :include-node? #{:element :characters :comment}))
     :indented-roundtrip (normalize-node (xml/parse-str indented
                                                        :include-node? #{:element :characters :comment}))
     :events (mapv event-shape (xml/event-seq (event-source source)
                                              {:include-node? #{:element
                                                               :characters
                                                               :comment}}))}))

(defn sexp-summary []
  {:single (normalize-node
            (xml/sexp-as-element
             [:root {:a "1"} "x" [:child "y"] [:-cdata "z < q"]
              [:-comment " note "]]))
   :fragment (mapv normalize-node
                   (xml/sexps-as-fragment
                    [:a "x"]
                    nil
                    :standalone
                    [:b "y"]
                    [:c "z"]))
   :empty-fragment? (nil? (xml/sexps-as-fragment))})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn generated-case [seed]
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
                                       (xml/cdata (str "c<" value))))
        emitted (xml/emit-str tree :declaration false)]
    {:seed seed
     :same-after-emit? (= (normalize-node tree)
                          (normalize-node (xml/parse-str emitted)))
     :same-after-events? (= (normalize-node tree)
                            (normalize-node
                             (tree/event-tree (tree/flatten-elements [tree]))))
     :event-count (count (tree/flatten-elements [tree]))
     :xmlns (sort
             (xml/find-xmlns
              (xml/element (xml/qname uri "root")
                           {(xml/qname attr-uri "id") value})))
     :next-seed s3}))

(defn generated-summary []
  (loop [remaining 64
         seed 871263
         result []]
    (if (zero? remaining)
      result
      (let [case (generated-case seed)]
        (recur (dec remaining)
               (:next-seed case)
               (conj result (dissoc case :next-seed)))))))
