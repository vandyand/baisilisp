;; Portable clojure.tools.namespace/basilisp.tools.namespace semantic coverage.
;;
;; The fixture compares data-oriented behavior and avoids host-specific path
;; strings. Runtime-specific setup creates temp files and archives, but emitted
;; values are normalized namespace names, booleans, and dependency sets.

(require '[clojure.java.io :as io]
         '[clojure.string :as str]
         '[clojure.tools.namespace :as namespace]
         '[clojure.tools.namespace.dependency :as dep]
         '[clojure.tools.namespace.dir :as dir]
         '[clojure.tools.namespace.file :as file]
         '[clojure.tools.namespace.find :as find]
         '[clojure.tools.namespace.move :as move]
         '[clojure.tools.namespace.parse :as parse]
         '[clojure.tools.namespace.reload :as reload]
         '[clojure.tools.namespace.repl :as repl]
         '[clojure.tools.namespace.track :as track]
         '[clojure.tools.reader.reader-types :as rt])

#?(:clj (import [java.io PushbackReader StringReader]
                [java.net URLClassLoader]
                [java.nio.file Files]
                [java.util.jar JarFile]
                [java.util.zip ZipEntry ZipOutputStream])
   :lpy (import [io :as py-io] sys tempfile zipfile))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn names [xs]
  (vec (sort (map str xs))))

(defn ordered-names [xs]
  (vec (map str xs)))

(defn topo-valid? [order edges]
  (let [positions (zipmap order (range))]
    (every? (fn [[node dependency]]
              (< (positions dependency) (positions node)))
            edges)))

(defn ns-name-str [decl]
  (some-> decl parse/name-from-ns-decl str))

(defn deps [decl]
  (names (parse/deps-from-ns-decl decl)))

(defn source-reader [source]
  (rt/string-push-back-reader source))

(defn root-source-reader [source]
  #?(:clj (PushbackReader. (StringReader. source))
     :lpy (source-reader source)))

(defn temp-root []
  #?(:clj (str (Files/createTempDirectory
                "basilisp-tools-namespace-case"
                (make-array java.nio.file.attribute.FileAttribute 0)))
     :lpy (tempfile/mkdtemp ** :prefix "basilisp-tools-namespace-case")))

(defn temp-file [root & parts]
  (apply io/file root parts))

(defn write-text! [file text]
  #?(:clj (.mkdirs (.getParentFile (io/file file)))
     :lpy (.mkdir (.-parent (io/file file)) ** :parents true :exist_ok true))
  (with-open [writer (io/writer file)]
    (.write writer text))
  file)

(defn mkdirs! [dir]
  #?(:clj (.mkdirs (io/file dir))
     :lpy (.mkdir (io/file dir) ** :parents true :exist_ok true))
  dir)

(defn read-text [file]
  (slurp file))

(defn exists? [file]
  #?(:clj (.exists (io/file file))
     :lpy (.exists (io/file file))))

(defn quiet-call [f]
  #?(:clj (let [result (atom nil)]
            (with-out-str
              (reset! result (f)))
            @result)
     :lpy (binding [*out* (py-io/StringIO)]
            (f))))

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
                     ["jarred/dep.cljc" "(ns jarred.dep)"
                     ]
                     ["jarred/ignored.txt" "(ns jarred.ignored)"]])
    {:root root :src src :jar jar}))

(defn create-classpath-tree! []
  (let [root (temp-root)
        jar  (temp-file root "archives" "classpath-fixture.jar")
        host-extension #?(:clj "clj" :lpy "lpy")]
    (write-text! (temp-file root "classpath_dir" (str "host." host-extension))
                 "(ns classpath-dir.host)")
    (write-text! (temp-file root "classpath_dir" "shared.cljc")
                 "(ns classpath-dir.shared)")
    (write-text! (temp-file root "classpath_dir" "ignored.txt")
                 "(ns classpath-dir.ignored)")
    (write-zip! jar [[(str "classpath_archive/host." host-extension)
                      "(ns classpath-archive.host)"]
                     ["classpath_archive/shared.cljc"
                      "(ns classpath-archive.shared)"]
                     ["classpath_archive/ignored.txt"
                      "(ns classpath-archive.ignored)"]])
    {:root root :jar jar}))

(defn compiler-loader-var []
  #?(:clj (.get (doto (.getDeclaredField (Class/forName "clojure.lang.Compiler")
                                          "LOADER")
                 (.setAccessible true))
                nil)
     :lpy nil))

(defn classpath-discovery-summary [root jar]
  #?(:clj
     (let [urls (into-array java.net.URL [(.toURL (.toURI (io/file root)))
                                          (.toURL (.toURI (io/file jar)))])
           loader (URLClassLoader. urls nil)]
       (with-bindings {(compiler-loader-var) loader}
         {:names (names (namespace/find-namespaces-on-classpath))
          :decls (names (map second (namespace/find-ns-decls-on-classpath)))}))
     :lpy
     (let [original-path (list sys/path)]
       (try
         (.clear sys/path)
         (.extend sys/path [(str root) (str jar)])
         {:names (names (namespace/find-namespaces-on-classpath))
          :decls (names (map second (namespace/find-ns-decls-on-classpath)))}
         (finally
           (.clear sys/path)
           (.extend sys/path original-path))))))

(emit-case :root-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.namespace
                                              :lpy 'basilisp.tools.namespace))
                               %)
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
                     find-namespaces-in-jarfile
                     find-ns-decls-on-classpath
                     find-namespaces-on-classpath]))

(emit-case :move-and-repl-public-surfaces
           {:move (names (keys (ns-publics 'clojure.tools.namespace.move)))
            :repl (names (keys (ns-publics 'clojure.tools.namespace.repl)))})

(emit-case :dependency-graph-semantics
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
             {:protocol-vars [(boolean dep/DependencyGraph)
                              (boolean dep/DependencyGraphUpdate)
                              #?(:clj true
                                 :lpy (contains? (ns-publics
                                                  'basilisp.tools.namespace.dependency)
                                                 'MapDependencyGraph))]
              :nodes (names (dep/nodes g1))
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
              :topo-sort (names (dep/topo-sort g1))
              :topo-comparator (mapv str (sort (dep/topo-comparator g1)
                                               ['feature.ui 'app.core 'lib.beta 'lib.alpha]))
              :record-type [(class? #?(:clj clojure.tools.namespace.dependency.MapDependencyGraph
                                        :lpy dep/MapDependencyGraph))
                            (instance? #?(:clj clojure.tools.namespace.dependency.MapDependencyGraph
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

(emit-case :adversarial-dependency-graph-updates
           (let [edges [['feature.ui 'app.core]
                        ['feature.ui 'lib.theme]
                        ['app.core 'lib.data]
                        ['app.core 'lib.util]
                        ['lib.theme 'lib.util]
                        ['lib.data 'lib.codec]]
                 graph (reduce (fn [g [node dependency]]
                                 (dep/depend g node dependency))
                               (dep/graph)
                               edges)
                 duplicate (dep/depend graph 'app.core 'lib.util)
                 without-edge (dep/remove-edge graph 'app.core 'lib.util)
                 without-all (dep/remove-all graph 'app.core)
                 without-node (dep/remove-node graph 'lib.theme)
                 removed-missing-edge (dep/remove-edge graph 'missing.node 'lib.util)
                 order (vec (dep/topo-sort graph))
                 duplicate-order (vec (dep/topo-sort duplicate))]
             {:nodes (names (dep/nodes graph))
              :duplicate-stable? (= (names (dep/immediate-dependencies graph 'app.core))
                                    (names (dep/immediate-dependencies duplicate 'app.core)))
              :topo-valid? (topo-valid? order edges)
              :duplicate-topo-valid? (topo-valid? duplicate-order edges)
              :transitive-feature (names (dep/transitive-dependencies
                                           graph 'feature.ui))
              :transitive-set (names (dep/transitive-dependencies-set
                                       graph #{'feature.ui 'app.core}))
              :dependent-codec (names (dep/transitive-dependents
                                        graph 'lib.codec))
              :removed-edge-deps (names (dep/immediate-dependencies
                                          without-edge 'app.core))
              :removed-all-nodes (names (dep/nodes without-all))
              :removed-node-nodes (names (dep/nodes without-node))
              :removed-missing-stable? (= (names (dep/nodes graph))
                                          (names (dep/nodes removed-missing-edge)))
              :self-cycle? (rejected? #(dep/depend graph 'app.core 'app.core))
              :deep-cycle? (rejected? #(dep/depend graph 'lib.codec 'feature.ui))}))

(emit-case :parse-semantics
           (let [source "(comment ignored)
                         (def before-ns :ignored)
                         (ns sample.parse
                           (:require [clojure.set :as set]
                                     [demo [alpha :as a] [beta]]
                                     #?(:clj [sample.clj-only] :lpy [sample.lpy-only])
                                     [sample.alias-only :as-alias alias])
                           (:use sample.used)
                           (:require-macros [sample.macro :refer [m]]))"
                 clj-decl (parse/read-ns-decl (source-reader source) parse/clj-read-opts)
                 cljs-decl (parse/read-ns-decl (source-reader source)
                                               parse/cljs-read-opts)
                 lpy-decl (parse/read-ns-decl (source-reader source)
                                              #?(:clj parse/clj-read-opts
                                                 :lpy parse/lpy-read-opts))]
             {:comment? (parse/comment? '(comment ignored))
              :ns-decl? (parse/ns-decl? clj-decl)
              :name (str (parse/name-from-ns-decl clj-decl))
              :clj-deps (deps clj-decl)
              :cljs-deps (deps cljs-decl)
              :host-reader-conditional?
              #?(:clj (contains? (set (deps lpy-decl)) "sample.clj-only")
                 :lpy (contains? (set (deps lpy-decl)) "sample.lpy-only"))
              :empty-read (nil? (parse/read-ns-decl (source-reader "(comment only)")))
              :unparsable-rejected? (rejected?
                                      #(parse/deps-from-ns-decl
                                        '(ns broken (:require [bad {:not :valid}]))))}))

(emit-case :adversarial-parse-libspecs
           (let [source "(comment ignored)
                         (ns sample.adversarial
                           \"docstring\"
                           {:author \"fixture\"}
                           (:refer-clojure :exclude [replace])
                           (:require
                            [alpha.core :refer [a] :rename {a aa}]
                            [beta.core :as beta]
                            [gamma [one] [two :as two] [three :refer :all]]
                            #?(:clj [host.selected] :lpy [host.selected])
                            [alias.target :as-alias alias]
                            \"npm-package\")
                           (:require-macros [macro.core :refer [m]]
                                            [macro.extra :as mx])
                           (:use [used.core :only [u]]
                                 used.extra)
                           (:import [java.util Date UUID])
                           (:gen-class))"
                 decl (parse/read-ns-decl (source-reader source)
                                          #?(:clj parse/clj-read-opts
                                             :lpy parse/lpy-read-opts))]
             {:name (str (parse/name-from-ns-decl decl))
              :deps (deps decl)
              :ignores-import? (not (contains? (set (deps decl)) "java.util"))
              :ignores-as-alias? (not (contains? (set (deps decl))
                                                 "alias.target"))
              :host-conditional? (contains? (set (deps decl)) "host.selected")
              :rejects-map-libspec? (rejected?
                                      #(parse/deps-from-ns-decl
                                        '(ns broken
                                           (:require [bad {:not :valid}]))))
              :rejects-nested-prefix? (rejected?
                                        #(parse/deps-from-ns-decl
                                          '(ns broken
                                             (:require [root [child [leaf]]]))))}))

(emit-case :file-find-and-dir-semantics
           (let [{:keys [src jar]} (create-source-tree!)
                 clj-files     file/clojure-extensions
                 cljs-files    file/clojurescript-extensions
                 basilisp-exts #?(:clj '(".lpy" ".cljc")
                                  :lpy file/basilisp-extensions)
                 core-file     (temp-file src "sample" "core.clj")
                 cljs-file     (temp-file src "sample" "script.cljs")
                 lpy-file      (temp-file src "sample" "native.lpy")
                 jar-ref       #?(:clj (JarFile. (io/file jar))
                                  :lpy jar)
                 clj-decls     (find/find-ns-decls-in-dir src find/clj)
                 clj-names     (find/find-namespaces-in-dir src find/clj)
                 all-decls     (find/find-ns-decls [src jar] find/clj)
                 file-tracker  (file/add-files (track/tracker) [core-file]
                                                parse/clj-read-opts)
                 removed-file-tracker (file/remove-files file-tracker [core-file])
                 tracker       (-> (track/tracker)
                                   (dir/scan-files [core-file] {:platform find/clj :add-all? true})
                                   (dir/scan-files [core-file cljs-file] {:platform find/clj})
                                   (dir/scan-all src))
                 dir-tracker   (dir/scan-dirs (track/tracker) [src]
                                              {:platform find/clj :add-all? true})
                 scan-tracker  (dir/scan (track/tracker) src)]
             {:extension-vars {:clj (vec clj-files)
                               :cljs (vec cljs-files)
                               :basilisp (vec basilisp-exts)}
              :file-predicates {:clojure-core (file/clojure-file? core-file)
                                :clojurescript-script (file/clojurescript-file? cljs-file)
                                :basilisp-native #?(:clj true
                                                   :lpy (file/basilisp-file? lpy-file))}
              :file-with-extension? (file/file-with-extension? core-file [".clj"])
              :read-file (ns-name-str (file/read-file-ns-decl core-file))
              :file-add-load (names (::track/load file-tracker))
              :file-remove-unload (names (::track/unload removed-file-tracker))
              :find-sources-count (count (find/find-sources-in-dir src find/clj))
              :find-cljs-sources-count (count (find/find-sources-in-dir src find/cljs))
              :find-lpy-extension-count #?(:clj 2
                                           :lpy (count (:extensions find/lpy)))
              :find-clojure-sources-count (count (find/find-clojure-sources-in-dir src))
              :find-ns-decls (names (map parse/name-from-ns-decl clj-decls))
              :find-namespaces (names clj-names)
              :find-combined-namespaces (names (find/find-namespaces [src jar] find/clj))
              :root-comment? (namespace/comment? '(comment ignored))
              :root-ns-decl? (namespace/ns-decl? '(ns sample.root))
              :root-read-ns (ns-name-str (namespace/read-ns-decl
                                           (root-source-reader "(ns sample.root)")))
              :root-find-clojure-sources-count
              (count (namespace/find-clojure-sources-in-dir src))
              :root-find-ns-decls (names (map parse/name-from-ns-decl
                                               (namespace/find-ns-decls-in-dir src)))
              :root-find-namespaces (names (namespace/find-namespaces-in-dir src))
              :root-read-file (ns-name-str (namespace/read-file-ns-decl core-file))
              :root-clojure-file? (namespace/clojure-source-file? core-file)
              :jar-sources (vec (find/sources-in-jar jar-ref find/clj))
              :jar-clojure-sources (vec (find/clojure-sources-in-jar jar-ref))
              :jar-entry (ns-name-str (find/read-ns-decl-from-jarfile-entry
                                       jar-ref "jarred/core.clj" find/clj))
              :jar-decls (names (map parse/name-from-ns-decl
                                      (find/find-ns-decls-in-jarfile jar-ref find/clj)))
              :jar-names (names (find/find-namespaces-in-jarfile jar-ref find/clj))
              :root-jar-sources (vec (namespace/clojure-sources-in-jar jar-ref))
              :root-jar-entry (ns-name-str (namespace/read-ns-decl-from-jarfile-entry
                                            jar-ref "jarred/core.clj"))
              :root-jar-decls (names (map parse/name-from-ns-decl
                                           (namespace/find-ns-decls-in-jarfile jar-ref)))
              :root-jar-names (names (namespace/find-namespaces-in-jarfile jar-ref))
              :combined (names (map parse/name-from-ns-decl all-decls))
              :tracker-load (names (::track/load tracker))
              :tracker-unload (names (::track/unload tracker))
              :dir-scan-load (names (::track/load dir-tracker))
              :scan-load (names (::track/load scan-tracker))}))

(emit-case :root-classpath-semantics
           (let [{:keys [root jar]} (create-classpath-tree!)]
             (classpath-discovery-summary root jar)))

(emit-case :move-namespace-semantics
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

(emit-case :repl-refresh-semantics
           (let [{:keys [src]} (create-source-tree!)
                 empty-dir (temp-file (temp-root) "empty")
                 probe-ns (create-ns 'tools.namespace.repl.probe)
                 _ (repl/clear)
                 set-dirs (repl/set-refresh-dirs src)
                 scanned (repl/scan {:platform find/clj :add-all? true})
                 scan-load (names (::track/load scanned))
                 disabled-unload (repl/disable-unload! probe-ns)
                 disabled-reload (repl/disable-reload! probe-ns)
                 invalid-after (rejected? #(quiet-call
                                             (fn []
                                               (repl/refresh-scanned
                                                :after
                                                'not-qualified))))
                 missing-after (rejected? #(quiet-call
                                             (fn []
                                               (repl/refresh-scanned
                                                :after
                                                'missing.ns/callback))))
                 empty-refresh (do
                                 (mkdirs! empty-dir)
                                 (repl/clear)
                                 (repl/set-refresh-dirs empty-dir)
                                 [(quiet-call #(repl/refresh-scanned))
                                  (quiet-call #(repl/refresh))
                                  (quiet-call #(repl/refresh-all))])
                 all-scan (do
                            (repl/clear)
                            (repl/set-refresh-dirs src)
                            (repl/scan {:platform find/clj :add-all? true}))]
             {:set-dirs-count (count set-dirs)
              :scan-load scan-load
              :refresh-dirs-count (count repl/refresh-dirs)
              :disabled [(false? (::repl/unload disabled-unload))
                         (false? (::repl/load disabled-reload))
                         (false? (::repl/unload disabled-reload))]
              :after-boundaries [invalid-after missing-after]
              :empty-refresh empty-refresh
              :refresh-scanned-direct (not (nil? all-scan))
              :refresh-tracker-direct (map? repl/refresh-tracker)
              :clear (empty? (repl/clear))
              :refresh-all-callable? (not (rejected?
                                           #(quiet-call repl/refresh-all)))}))

(emit-case :track-and-reload-semantics
           (let [tracker0 (track/tracker)
                 tracker1 (track/add tracker0 {'sample.core #{'sample.dep}
                                               'sample.dep #{'sample.util}})
                 tracker2 (track/add tracker1 {'sample.util #{}})
                 tracker3 (track/remove tracker2 ['sample.dep])
                 tracker4 (reload/track-reload-one {::track/unload ['missing.ns]
                                                     ::track/load []})
                 tracker5 (reload/track-reload {::track/unload []
                                                ::track/load []})]
             {:tracker-empty tracker0
              :add-load (names (::track/load tracker2))
              :add-unload (names (::track/unload tracker2))
              :remove-load (names (::track/load tracker3))
              :remove-unload (names (::track/unload tracker3))
              :reload-remove-lib-called? (empty? (::track/unload tracker4))
              :reload-noop {:load (names (::track/load tracker5))
                             :unload (names (::track/unload tracker5))}
              :reload-remove-direct
              (not (rejected? #(reload/remove-lib 'definitely.missing.ns)))}))
