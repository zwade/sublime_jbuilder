open Core
open Async
    
module J = Jbuild_fmt
  
let find_all_jbuild ~root =
  let%bind is_root_a_directory = Sys.is_directory root in
  begin
    match is_root_a_directory with
    | `No | `Unknown ->
      raise_s [%sexp (root:Path.t), "Is not a directory"];
    | _ -> ()
  end;
  let rec find_in_tree base =
    let%bind files = Sys.ls_dir base in
    let%map result = 
      Deferred.List.map files ~f:(fun file ->
          let path = base ^/ file in
          match%bind Sys.is_directory ~follow_symlinks:true path with
          | `Yes -> find_in_tree path
          | _    -> 
            if String.is_suffix file ~suffix:"jbuild"
            then return [base]
            else return [])
    in
    result
    |> List.concat
  in
  find_in_tree root
;;

let targets_by_path jbuild_roots =
  let target_map = Path.Table.create () in
  let results = 
    Deferred.List.iter jbuild_roots ~f:(fun root_path ->
        let%map targets = Reader.load_sexps (root_path ^/ "jbuild") ([%of_sexp: Jbuild_fmt.t]) in
        match targets with
        | Error e -> raise_s [%sexp "Error reading jbuild file: ", (e : Error.t)]
        | Ok x    -> 
          Hashtbl.set target_map ~key:root_path ~data:x) 
      
  in
  let%map () = results in
  target_map
    
let run root () =
  let%bind jbuilds = find_all_jbuild ~root in
  let%map targets = targets_by_path jbuilds in
  printf !"Found: %{sexp:Path.t list}\n" jbuilds;
  printf !"Found targets: %{sexp:Jbuild_fmt.t list Path.Table.t}" targets
    

let command_find = Command.async' ~summary:"Find all jbuild files" 
    begin
      let open Command.Let_syntax in
      let%map_open root = flag "-root" (required file) ~doc:"directory The directory to search for jbuilds in" in
      run root
    end
    
let command = Command.group ~summary:"Operations for dealing with jbuild files"
    [ "find", command_find
    ]
    

let () = Command.run command