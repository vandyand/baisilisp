(ns acceptance.tools-namespace.workflow
  (:require [clojure.java.io :as io]
            [clojure.tools.namespace :as namespace]
            [clojure.tools.namespace.dependency :as dep]
            [clojure.tools.namespace.dir :as dir]
            [clojure.tools.namespace.file :as file]
            [clojure.tools.namespace.find :as find]
            [clojure.tools.namespace.move :as move]
            [clojure.tools.namespace.parse :as parse]
            [clojure.tools.namespace.track :as track]
            [clojure.tools.reader.reader-types :as rt]))

#?(:clj (import [java.io PushbackReader StringReader]
                [java.nio.file Files]
                [java.util.jar JarFile]
                [java.util.zip ZipEntry ZipOutputStream])
   :lpy (import tempfile zipfile))

(def selected-publics
  [['clojure.tools.namespace
    '[clojure-source-file?
      find-clojure-sources-in-dir
      comment?
      ns-decl?
      read-ns-decl
      read-file-ns-decl
      find-ns-decls-in-dir
      find-namespaces-in-dir
      clojure-sources-in-jar
      read-ns-decl-from-jarfile-entry
      find-ns-decls-in-jarfile
      find-namespaces-in-jarfile]]
   ['clojure.tools.namespace.dependency
    '[DependencyGraph
      DependencyGraphUpdate
      ->MapDependencyGraph
      map->MapDependencyGraph
      graph
      depend
      depends?
      dependent?
      immediate-dependencies
      immediate-dependents
      nodes
      remove-all
      remove-edge
      remove-node
      set-conj
      topo-comparator
      topo-sort
      transitive-dependencies
      transitive-dependencies-set
      transitive-dependents
      transitive-dependents-set]]
   ['clojure.tools.namespace.dir
    '[scan scan-all scan-dirs scan-files]]
   ['clojure.tools.namespace.file
    '[add-files
      clojure-extensions
      clojure-file?
      clojurescript-extensions
      clojurescript-file?
      file-with-extension?
      read-file-ns-decl
      remove-files]]
   ['clojure.tools.namespace.find
    '[clj
      cljs
      find-clojure-sources-in-dir
      find-namespaces
      find-namespaces-in-dir
      find-namespaces-in-jarfile
      find-ns-decls
      find-ns-decls-in-dir
      find-ns-decls-in-jarfile
      find-sources-in-dir
      read-ns-decl-from-jarfile-entry
      sources-in-jar]]
   ['clojure.tools.namespace.move
    '[move-ns move-ns-file replace-ns-symbol]]
   ['clojure.tools.namespace.parse
    '[clj-read-opts
      cljs-read-opts
      comment?
      deps-from-ns-decl
      name-from-ns-decl
      ns-decl?
      read-ns-decl]]
   ['clojure.tools.namespace.track
    '[add remove tracker]]])

(defn names [xs]
  (vec (sort (map str xs))))

(defn ordered-names [xs]
  (vec (map str xs)))

(defn public-summary []
  (into []
        (map (fn [[ns-sym publics]]
               [(str ns-sym)
                (into []
                      (map (fn [sym]
                             [sym (contains? (ns-publics ns-sym) sym)])
                           publics))])
             selected-publics)))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn source-reader [source]
  (rt/string-push-back-reader source))

(defn root-source-reader [source]
  #?(:clj (PushbackReader. (StringReader. source))
     :lpy (source-reader source)))

(defn deps [decl]
  (names (parse/deps-from-ns-decl decl)))

(defn ns-name [decl]
  (some-> decl parse/name-from-ns-decl str))

(defn parse-summary []
  (let [source "(comment ignored)
                (def before-ns :ignored)
                (ns acceptance.sample
                  \"docstring\"
                  {:author \"fixture\"}
                  (:refer-clojure :exclude [replace])
                  (:require
                   [alpha.core :refer [a] :rename {a aa}]
                   [beta.core :as beta]
                   [gamma [one] [two :as two] [three :refer :all]]
                   #?(:clj [host.clj] :lpy [host.lpy])
                   [alias.target :as-alias alias]
                   \"npm-package\")
                  (:require-macros [macro.core :refer [m]]
                                   [macro.extra :as mx])
                  (:use [used.core :only [u]]
                        used.extra)
                  (:import [java.util Date UUID]))"
        clj-decl (parse/read-ns-decl (source-reader source) parse/clj-read-opts)
        cljs-decl (parse/read-ns-decl (source-reader source) parse/cljs-read-opts)
        host-decl (parse/read-ns-decl (source-reader source)
                                      #?(:clj parse/clj-read-opts
                                         :lpy parse/lpy-read-opts))
        host-deps (set (deps host-decl))]
    {:comment? (parse/comment? '(comment ignored))
     :ns-decl? (parse/ns-decl? clj-decl)
     :name (ns-name clj-decl)
     :root-name (ns-name (namespace/read-ns-decl
                          (root-source-reader "(ns acceptance.root)")))
     :clj-deps (deps clj-decl)
     :cljs-deps (deps cljs-decl)
     :host-conditional? #?(:clj (contains? host-deps "host.clj")
                           :lpy (contains? host-deps "host.lpy"))
     :ignores-import? (not (contains? (set (deps clj-decl)) "java.util"))
     :ignores-as-alias? (not (contains? (set (deps clj-decl)) "alias.target"))
     :empty-read (nil? (parse/read-ns-decl (source-reader "(comment only)")))
     :bad-libspec-rejected? (rejected?
                             #(parse/deps-from-ns-decl
                               '(ns broken (:require [bad {:not :valid}]))))
     :nested-prefix-rejected? (rejected?
                               #(parse/deps-from-ns-decl
                                 '(ns broken
                                    (:require [root [child [leaf]]]))))}))

(defn topo-valid? [order edges]
  (let [positions (zipmap order (range))]
    (every? (fn [[node dependency]]
              (< (positions dependency) (positions node)))
            edges)))

(defn dependency-summary []
  (let [g0 (dep/graph)
        g1 (-> g0
               (dep/depend 'app.core 'lib.alpha)
               (dep/depend 'app.core 'lib.beta)
               (dep/depend 'lib.beta 'lib.alpha)
               (dep/depend 'feature.ui 'app.core))
        g2 (dep/remove-edge g1 'app.core 'lib.alpha)
        g3 (dep/remove-all g1 'app.core)
        g4 (dep/remove-node g1 'lib.beta)
        g5 (dep/->MapDependencyGraph {'x #{'y}} {'y #{'x}})
        g6 (dep/map->MapDependencyGraph {:dependencies {'z #{'x}}
                                         :dependents {'x #{'z}}})]
    {:nodes (names (dep/nodes g1))
     :immediate-dependencies (names (dep/immediate-dependencies g1 'app.core))
     :immediate-dependents (names (dep/immediate-dependents g1 'lib.alpha))
     :transitive-dependencies (names (dep/transitive-dependencies g1 'feature.ui))
     :transitive-dependencies-set (names (dep/transitive-dependencies-set
                                          g1 #{'feature.ui 'app.core}))
     :transitive-dependents (names (dep/transitive-dependents g1 'lib.alpha))
     :transitive-dependents-set (names (dep/transitive-dependents-set
                                        g1 #{'lib.alpha}))
     :depends? (dep/depends? g1 'feature.ui 'lib.alpha)
     :dependent? (dep/dependent? g1 'lib.alpha 'feature.ui)
     :remove-edge (names (dep/immediate-dependencies g2 'app.core))
     :remove-all-nodes (names (dep/nodes g3))
     :remove-node-nodes (names (dep/nodes g4))
     :topo-sort-valid? (topo-valid? (vec (dep/topo-sort g1))
                                    [['app.core 'lib.alpha]
                                     ['app.core 'lib.beta]
                                     ['lib.beta 'lib.alpha]
                                     ['feature.ui 'app.core]])
     :topo-comparator (ordered-names
                       (sort (dep/topo-comparator g1)
                             ['feature.ui 'app.core 'lib.beta 'lib.alpha]))
     :record [(instance? #?(:clj clojure.tools.namespace.dependency.MapDependencyGraph
                            :lpy dep/MapDependencyGraph)
                         g5)
              (instance? #?(:clj clojure.tools.namespace.dependency.MapDependencyGraph
                            :lpy dep/MapDependencyGraph)
                         g6)
              (satisfies? dep/DependencyGraph g5)
              (satisfies? dep/DependencyGraphUpdate g6)]
     :constructed (names (dep/immediate-dependencies g5 'x))
     :mapped (names (dep/immediate-dependents g6 'x))
     :set-conj (dep/set-conj nil 'x)
     :cycle-rejected? (rejected? #(dep/depend g1 'lib.alpha 'feature.ui))}))

(defn next-seed [seed]
  (mod (+ (* 1103515245 seed) 12345) 2147483648))

(defn generated-edges [seed]
  (let [nodes (vec (map #(symbol (str "generated.n" %)) (range 9)))]
    (loop [remaining 8
           current seed
           index 0
           edges []]
      (if (zero? remaining)
        edges
        (let [next (next-seed current)]
          (recur (dec remaining)
                 next
                 (inc index)
                 (if (pos? (mod next 3))
                   (conj edges [(nth nodes index) (nth nodes (inc index))])
                   edges)))))))

(defn graph-check [seed]
  (let [edges (generated-edges seed)
        graph (reduce (fn [g [node dependency]]
                        (dep/depend g node dependency))
                      (dep/graph)
                      edges)
        order (vec (dep/topo-sort graph))
        tracker (track/add (track/tracker)
                           (into {}
                                 (for [node (distinct (mapcat identity edges))]
                                   [node (set (map second
                                                   (filter #(= node (first %))
                                                           edges)))])))]
    {:edge-count (count edges)
     :topo-valid? (topo-valid? order edges)
     :load-valid? (topo-valid? (vec (::track/load tracker)) edges)
     :unload-valid? (topo-valid? (vec (reverse (::track/unload tracker))) edges)
     :nodes (names (dep/nodes graph))}))

(defn generated-graph-summary []
  (mapv graph-check (take 48 (iterate next-seed 20260731))))

(defn temp-root []
  #?(:clj (str (Files/createTempDirectory
                "basilisp-tools-namespace-acceptance"
                (make-array java.nio.file.attribute.FileAttribute 0)))
     :lpy (tempfile/mkdtemp ** :prefix "basilisp-tools-namespace-acceptance")))

(defn temp-file [root & parts]
  (apply io/file root parts))

(defn write-text! [file text]
  #?(:clj (.mkdirs (.getParentFile (io/file file)))
     :lpy (.mkdir (.-parent (io/file file)) ** :parents true :exist_ok true))
  (with-open [writer (io/writer file)]
    (.write writer text))
  file)

(defn write-zip! [file entries]
  #?(:clj
     (do
       (.mkdirs (.getParentFile (io/file file)))
       (with-open [stream (ZipOutputStream. (io/output-stream file))]
         (doseq [[entry-name text] entries]
           (.putNextEntry stream (ZipEntry. entry-name))
           (.write stream (.getBytes text "UTF-8"))
           (.closeEntry stream))))
     :lpy
     (do
       (.mkdir (.-parent (io/file file)) ** :parents true :exist_ok true)
       (with-open [archive (zipfile/ZipFile file "w")]
         (doseq [[entry-name text] entries]
           (.writestr archive entry-name text)))))
  file)

(defn create-source-tree! []
  (let [root (temp-root)
        src  (temp-file root "src")
        jar  (temp-file root "archives" "fixture.jar")]
    (write-text! (temp-file src "sample" "core.clj")
                 "(ns sample.core (:require [sample.dep :as dep] [clojure.set :as set]))")
    (write-text! (temp-file src "sample" "dep.cljc")
                 "(comment ignored) (ns sample.dep (:require #?(:clj [sample.clj-only] :lpy [sample.lpy-only]) [sample.shared]))")
    (write-text! (temp-file src "sample" "script.cljs")
                 "(ns sample.script (:require [sample.cljs-only]))")
    (write-text! (temp-file src "sample" "native.lpy")
                 "(ns sample.native (:require [sample.dep]))")
    (write-text! (temp-file src "sample" "ignored.txt")
                 "(ns sample.ignored)")
    (write-zip! jar [["jarred/core.clj" "(ns jarred.core (:require [jarred.dep]))"]
                     ["jarred/dep.cljc" "(ns jarred.dep)"]
                     ["jarred/ignored.txt" "(ns jarred.ignored)"]])
    {:src src :jar jar}))

(defn source-discovery-summary []
  (let [{:keys [src jar]} (create-source-tree!)
        core-file (temp-file src "sample" "core.clj")
        cljs-file (temp-file src "sample" "script.cljs")
        lpy-file (temp-file src "sample" "native.lpy")
        jar-ref #?(:clj (JarFile. (io/file jar))
                   :lpy jar)
        tracker (-> (track/tracker)
                    (dir/scan-files [core-file] {:platform find/clj :add-all? true})
                    (dir/scan-files [core-file cljs-file] {:platform find/clj})
                    (dir/scan-all src))]
    {:extensions {:clj (vec file/clojure-extensions)
                  :cljs (vec file/clojurescript-extensions)
                  :lpy #?(:clj [".lpy" ".cljc"]
                          :lpy (vec file/basilisp-extensions))}
     :file-predicates {:clj (file/clojure-file? core-file)
                       :cljs (file/clojurescript-file? cljs-file)
                       :lpy #?(:clj true :lpy (file/basilisp-file? lpy-file))}
     :file-with-extension? (file/file-with-extension? core-file [".clj"])
     :read-file (ns-name (file/read-file-ns-decl core-file))
     :find-sources-count (count (find/find-sources-in-dir src find/clj))
     :find-cljs-sources-count (count (find/find-sources-in-dir src find/cljs))
     :find-ns-decls (names (map parse/name-from-ns-decl
                                 (find/find-ns-decls-in-dir src find/clj)))
     :find-namespaces (names (find/find-namespaces-in-dir src find/clj))
     :root-comment? (namespace/comment? '(comment ignored))
     :root-ns-decl? (namespace/ns-decl? '(ns sample.root))
     :root-read-ns (ns-name (namespace/read-ns-decl
                             (root-source-reader "(ns sample.root)")))
     :root-find-clojure-sources-count (count (namespace/find-clojure-sources-in-dir src))
     :root-find-namespaces (names (namespace/find-namespaces-in-dir src))
     :root-read-file (ns-name (namespace/read-file-ns-decl core-file))
     :root-clojure-file? (namespace/clojure-source-file? core-file)
     :jar-sources (vec (find/sources-in-jar jar-ref find/clj))
     :jar-clojure-sources (vec (find/clojure-sources-in-jar jar-ref))
     :jar-entry (ns-name (find/read-ns-decl-from-jarfile-entry
                          jar-ref "jarred/core.clj" find/clj))
     :jar-names (names (find/find-namespaces-in-jarfile jar-ref find/clj))
     :root-jar-sources (vec (namespace/clojure-sources-in-jar jar-ref))
     :root-jar-entry (ns-name (namespace/read-ns-decl-from-jarfile-entry
                               jar-ref "jarred/core.clj"))
     :root-jar-names (names (namespace/find-namespaces-in-jarfile jar-ref))
     :tracker-load (names (::track/load tracker))
     :tracker-unload (names (::track/unload tracker))}))

(defn exists? [file]
  #?(:clj (.exists (io/file file))
     :lpy (.exists (io/file file))))

(defn read-text [file]
  (slurp file))

(defn move-summary []
  (let [file-root (temp-root)
        file-src (temp-file file-root "src")
        file-old (temp-file file-src "old" "core.clj")
        file-new (temp-file file-src "new" "core.clj")
        tree-root (temp-root)
        tree-src (temp-file tree-root "src")
        old-file (temp-file tree-src "old" "core.clj")
        other-file (temp-file tree-src "other" "usage.clj")
        near-file (temp-file tree-src "other" "near.clj")
        new-file (temp-file tree-src "new" "core.clj")]
    (write-text! file-old
                 "(ns old.core)\n(def target 'old.core)\n")
    {:replace [(move/replace-ns-symbol
                "(ns old.core) old.core old.core-extra :old.core/value"
                'old.core
                'new.core)
               (move/replace-ns-symbol
                "old.core-extra old.core old.core$ old.core?"
                'old.core
                'new.core)]
     :move-file (do
                  (move/move-ns-file 'old.core 'new.core file-src)
                  [(not (exists? file-old))
                   (exists? file-new)
                   (read-text file-new)])
     :move-tree (do
                  (write-text! old-file
                               "(ns old.core)\n(def target 'old.core)\n")
                  (write-text! other-file
                               "(ns other.usage (:require [old.core :as old]))\n(def q 'old.core)\n")
                  (write-text! near-file
                               "(ns old.core-extra)\n(def s \"old.core\")\n(def k :old.core/value)\n")
                  (move/move-ns 'old.core 'new.core tree-src [tree-src])
                  [(not (exists? old-file))
                   (exists? new-file)
                   (read-text new-file)
                   (read-text other-file)
                   (read-text near-file)])}))
