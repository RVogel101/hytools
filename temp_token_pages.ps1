$terms=@("\u056F\u056E","\u0574\u056E","\u057A\u056B\u057F\u056B","\u0561\u0571\u0565","\u056F\u0572","\u0578\u0579","\u0561\u056C\u0565\u0575","\u0578\u0572\u0576","\u0576\u0565\u0576\u0565\u0570","\u0561\u056C","\u0565\u056C","\u0561\u057E","\u0565\u0571","\u0565\u0565\u0568\u0576","\u0574\u0565\u0563","\u057F\u0578\u0576","\u0576\u0578\u0575\u0576","\u0561\u0575\u056C\u0567\u0574")
$base='data/textbook_ocr_improved'
foreach($term in $terms){
    $pages = Get-ChildItem -Path $base -Filter 'page_*.txt' | Where-Object {
        Select-String -Path $_.FullName -Pattern $term -SimpleMatch -Quiet
    } | ForEach-Object { $_.Name }
    $pages = $pages | Sort-Object { [int]($_ -replace 'page_(\d+)\.txt','$1') }
    Write-Output "$term,$($pages.Count),$($pages -join ' ')"
}
