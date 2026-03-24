param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$DestinationPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem

$MainNs = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
$Columns = @(
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K",
    "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"
)

$ErrorMap = @{
    "VALIDATION_ERROR"                = @{ Status = 400; Message = "입력값이 올바르지 않습니다." }
    "INVALID_QUERY_PARAM"             = @{ Status = 400; Message = "유효하지 않은 쿼리 파라미터입니다." }
    "INVALID_ORDERING"                = @{ Status = 400; Message = "지원하지 않는 정렬 기준입니다." }
    "INVALID_CODE"                    = @{ Status = 400; Message = "인증 코드가 올바르지 않습니다." }
    "CODE_EXPIRED"                    = @{ Status = 400; Message = "인증 코드가 만료되었습니다." }
    "SOCIAL_USER_ONLY"                = @{ Status = 400; Message = "소셜 로그인 계정은 비밀번호 재설정을 지원하지 않습니다." }
    "REFRESH_TOKEN_MISSING"           = @{ Status = 400; Message = "refresh 토큰이 누락되었습니다." }
    "INVALID_FILE_TYPE"               = @{ Status = 400; Message = "지원하지 않는 파일 형식입니다. (jpg, jpeg, png, webp만 허용)" }
    "FILE_TOO_LARGE"                  = @{ Status = 400; Message = "파일 크기가 제한을 초과했습니다. (최대 5MB)" }
    "UNDERAGE"                        = @{ Status = 400; Message = "만 18세 미만은 성인 인증을 완료할 수 없습니다." }
    "ALREADY_VERIFIED"                = @{ Status = 400; Message = "이미 성인 인증이 완료된 계정입니다." }
    "JOB_TYPE_MISSING"                = @{ Status = 400; Message = "job_type이 누락되었습니다." }
    "BASE_WEIGHT_INVALID"             = @{ Status = 400; Message = "base_weight는 0보다 커야 합니다." }
    "MULTIPLIER_INVALID"              = @{ Status = 400; Message = "multiplier는 0보다 커야 합니다." }
    "SEARCH_QUERY_MISSING"            = @{ Status = 400; Message = "search_query가 누락되었습니다." }
    "GAME_ID_OR_SOURCE_MISSING"       = @{ Status = 400; Message = "game_id 또는 source가 누락되었습니다." }
    "GAME_ID_OR_STORE_ID_MISSING"     = @{ Status = 400; Message = "game_id 또는 store_id가 누락되었습니다." }
    "INVALID_GENRE_ID"                = @{ Status = 400; Message = "존재하지 않는 장르 ID가 포함되어 있습니다." }
    "INVALID_PLATFORM_ID"             = @{ Status = 400; Message = "존재하지 않는 플랫폼 ID가 포함되어 있습니다." }
    "INVALID_TAG_ID"                  = @{ Status = 400; Message = "존재하지 않는 태그 ID가 포함되어 있습니다." }
    "INVALID_REACTION"                = @{ Status = 400; Message = "reaction은 like, dislike, neutral 중 하나여야 합니다." }
    "REACTION_DATA_REQUIRED"          = @{ Status = 400; Message = "is_saved 또는 reaction 중 하나 이상 필요합니다." }
    "INVALID_SOURCE"                  = @{ Status = 400; Message = "유효하지 않은 source 값입니다." }
    "PREFERENCE_FIELDS_REQUIRED"      = @{ Status = 400; Message = "genre_ids, platform_ids, tag_ids는 필수 항목입니다." }
    "INVALID_STATE"                   = @{ Status = 400; Message = "유효하지 않은 state 파라미터입니다." }
    "OAUTH_CALLBACK_ERROR"            = @{ Status = 400; Message = "카카오 인증에 실패했습니다." }
    "DISCORD_OAUTH_CALLBACK_ERROR"    = @{ Status = 400; Message = "디스코드 인증에 실패했습니다." }
    "ADULT_VERIFICATION_CALLBACK_ERROR" = @{ Status = 400; Message = "비바톤 인증에 실패했습니다." }
    "ACCOUNT_NOT_DELETED"             = @{ Status = 400; Message = "탈퇴한 계정만 복구할 수 있습니다." }
    "ACCOUNT_RESTORE_EXPIRED"         = @{ Status = 400; Message = "탈퇴 후 7일이 지나 계정을 복구할 수 없습니다." }
    "UNAUTHORIZED"                    = @{ Status = 401; Message = "인증이 필요합니다." }
    "INVALID_CREDENTIALS"             = @{ Status = 401; Message = "이메일 또는 비밀번호가 올바르지 않습니다." }
    "INVALID_PASSWORD"                = @{ Status = 401; Message = "비밀번호가 올바르지 않습니다." }
    "ACCOUNT_DEACTIVATED"             = @{ Status = 401; Message = "비활성화된 계정입니다." }
    "TOKEN_EXPIRED"                   = @{ Status = 401; Message = "액세스 토큰이 만료되었습니다." }
    "INVALID_REFRESH_TOKEN"           = @{ Status = 401; Message = "유효하지 않은 리프레시 토큰입니다." }
    "REFRESH_TOKEN_EXPIRED"           = @{ Status = 401; Message = "리프레시 토큰이 만료되었습니다." }
    "RECOMMENDATION_NOT_READY"        = @{ Status = 202; Message = "추천 데이터를 준비중입니다 잠시 후 다시 요청해주세요." }
    "FORBIDDEN"                       = @{ Status = 403; Message = "관리자 권한이 필요합니다." }
    "CSRF_FAILED"                     = @{ Status = 403; Message = "CSRF 검증에 실패했습니다." }
    "ADULT_VERIFICATION_REQUIRED"     = @{ Status = 403; Message = "성인 인증이 필요한 게임입니다." }
    "GAME_NOT_FOUND"                  = @{ Status = 404; Message = "게임을 찾을 수 없습니다." }
    "STORE_NOT_FOUND"                 = @{ Status = 404; Message = "스토어를 찾을 수 없습니다." }
    "JOB_NOT_FOUND"                   = @{ Status = 404; Message = "작업을 찾을 수 없습니다." }
    "INTERACTION_TYPE_NOT_FOUND"      = @{ Status = 404; Message = "해당 interaction_type을 찾을 수 없습니다." }
    "SOURCE_NOT_FOUND"                = @{ Status = 404; Message = "해당 source를 찾을 수 없습니다." }
    "USER_NOT_FOUND"                  = @{ Status = 404; Message = "사용자를 찾을 수 없습니다." }
    "SEARCH_KEYWORD_NOT_FOUND"        = @{ Status = 404; Message = "해당 검색어를 찾을 수 없습니다." }
    "EMAIL_ALREADY_EXISTS"            = @{ Status = 409; Message = "이미 사용 중인 이메일입니다." }
    "NICKNAME_ALREADY_EXISTS"         = @{ Status = 409; Message = "이미 사용 중인 닉네임입니다." }
    "VERIFICATION_ALREADY_USED"       = @{ Status = 409; Message = "이미 사용된 인증 정보입니다. (provider_uid 중복)" }
    "JOB_ALREADY_RUNNING"             = @{ Status = 409; Message = "이미 실행 중인 작업이 있습니다." }
    "TOO_MANY_REQUESTS"               = @{ Status = 429; Message = "잠시 후 다시 시도해주세요." }
    "SERVER_ERROR"                    = @{ Status = 500; Message = "서버 오류가 발생했습니다." }
    "OAUTH_ERROR"                     = @{ Status = 500; Message = "OAuth 처리 중 오류가 발생했습니다." }
}

function Get-StatusLabel {
    param([int]$StatusCode)

    switch ($StatusCode) {
        200 { return "200 OK" }
        201 { return "201 Created" }
        202 { return "202 Accepted" }
        302 { return "302 Found" }
        400 { return "400 Bad Request" }
        401 { return "401 Unauthorized" }
        403 { return "403 Forbidden" }
        404 { return "404 Not Found" }
        409 { return "409 Conflict" }
        429 { return "429 Too Many Requests" }
        500 { return "500 Internal Server Error" }
        default { return [string]$StatusCode }
    }
}

function Format-StatusCodes {
    param([int[]]$Codes)

    return (($Codes | ForEach-Object { Get-StatusLabel $_ }) -join "`n")
}

function Format-ErrorExamples {
    param([string[]]$Codes)

    $blocks = foreach ($code in $Codes) {
        $error = $ErrorMap[$code]
        if (-not $error) {
            throw "Unknown error code: $code"
        }

        @"
// $(Get-StatusLabel $error.Status)
{
  "status_code": $($error.Status),
  "code": "$code",
  "message": "$($error.Message)"
}
"@
    }

    return ($blocks -join "`n`n")
}

function Get-ColumnIndex {
    param([string]$CellReference)

    $letters = ($CellReference -replace "\d", "").ToUpperInvariant()
    $index = 0
    foreach ($char in $letters.ToCharArray()) {
        $index = ($index * 26) + ([int][char]$char - [int][char]'A' + 1)
    }
    return $index
}

function Ensure-RowNode {
    param(
        [xml]$SheetXml,
        [System.Xml.XmlNamespaceManager]$NsMgr,
        [int]$RowNumber
    )

    $row = $SheetXml.SelectSingleNode("//x:sheetData/x:row[@r='$RowNumber']", $NsMgr)
    if ($row) {
        return $row
    }

    $sheetData = $SheetXml.SelectSingleNode("//x:sheetData", $NsMgr)
    $row = $SheetXml.CreateElement("row", $MainNs)
    [void]$row.SetAttribute("r", [string]$RowNumber)

    $inserted = $false
    foreach ($existing in @($sheetData.SelectNodes("x:row", $NsMgr))) {
        if ([int]$existing.r -gt $RowNumber) {
            [void]$sheetData.InsertBefore($row, $existing)
            $inserted = $true
            break
        }
    }

    if (-not $inserted) {
        [void]$sheetData.AppendChild($row)
    }

    return $row
}

function Ensure-CellNode {
    param(
        [xml]$SheetXml,
        [System.Xml.XmlNamespaceManager]$NsMgr,
        [string]$CellReference
    )

    $cell = $SheetXml.SelectSingleNode("//x:c[@r='$CellReference']", $NsMgr)
    if ($cell) {
        return $cell
    }

    $rowNumber = [int]($CellReference -replace "^[A-Z]+", "")
    $row = Ensure-RowNode -SheetXml $SheetXml -NsMgr $NsMgr -RowNumber $rowNumber
    $cell = $SheetXml.CreateElement("c", $MainNs)
    [void]$cell.SetAttribute("r", $CellReference)

    $targetIndex = Get-ColumnIndex $CellReference
    $inserted = $false
    foreach ($existing in @($row.SelectNodes("x:c", $NsMgr))) {
        if ((Get-ColumnIndex $existing.r) -gt $targetIndex) {
            [void]$row.InsertBefore($cell, $existing)
            $inserted = $true
            break
        }
    }

    if (-not $inserted) {
        [void]$row.AppendChild($cell)
    }

    return $cell
}

function Clear-CellValue {
    param(
        [xml]$SheetXml,
        [System.Xml.XmlNamespaceManager]$NsMgr,
        [string]$CellReference
    )

    $cell = $SheetXml.SelectSingleNode("//x:c[@r='$CellReference']", $NsMgr)
    if (-not $cell) {
        return
    }

    foreach ($childName in @("v", "is", "f")) {
        foreach ($child in @($cell.SelectNodes("x:$childName", $NsMgr))) {
            [void]$cell.RemoveChild($child)
        }
    }

    if ($cell.HasAttribute("t")) {
        [void]$cell.RemoveAttribute("t")
    }
}

function Set-CellText {
    param(
        [xml]$SheetXml,
        [System.Xml.XmlNamespaceManager]$NsMgr,
        [string]$CellReference,
        [string]$Text
    )

    if ([string]::IsNullOrEmpty($Text)) {
        Clear-CellValue -SheetXml $SheetXml -NsMgr $NsMgr -CellReference $CellReference
        return
    }

    $cell = Ensure-CellNode -SheetXml $SheetXml -NsMgr $NsMgr -CellReference $CellReference
    foreach ($childName in @("v", "is", "f")) {
        foreach ($child in @($cell.SelectNodes("x:$childName", $NsMgr))) {
            [void]$cell.RemoveChild($child)
        }
    }

    [void]$cell.SetAttribute("t", "inlineStr")
    $isNode = $SheetXml.CreateElement("is", $MainNs)
    $tNode = $SheetXml.CreateElement("t", $MainNs)
    $xmlNs = $SheetXml.CreateAttribute("xml", "space", "http://www.w3.org/XML/1998/namespace")
    $xmlNs.Value = "preserve"
    [void]$tNode.Attributes.Append($xmlNs)
    $tNode.InnerText = $Text
    [void]$isNode.AppendChild($tNode)
    [void]$cell.AppendChild($isNode)
}

function Clear-RowRange {
    param(
        [xml]$SheetXml,
        [System.Xml.XmlNamespaceManager]$NsMgr,
        [int]$RowNumber,
        [string[]]$ColumnsToClear
    )

    foreach ($column in $ColumnsToClear) {
        Clear-CellValue -SheetXml $SheetXml -NsMgr $NsMgr -CellReference "$column$RowNumber"
    }
}

$jsonMessageSchema = @'
{
  "message": "string"
}
'@

$loginSuccessExample = @'
{
  "message": "로그인 되었습니다."
}
'@

$refreshSuccessExample = @'
{
  "message": "액세스 토큰이 갱신되었습니다."
}
'@

$csrfSuccessSchema = @'
{
  "csrf_token": "string"
}
'@

$csrfSuccessExample = @'
{
  "csrf_token": "<token>"
}
'@

$authHeaderJsonCsrf = "Content-Type: application/json`nX-CSRFToken: {csrftoken}"
$csrfHeader = "X-CSRFToken: {csrftoken}"
$multipartCsrfHeader = "Content-Type: multipart/form-data`nX-CSRFToken: {csrftoken}"

$updates = [ordered]@{
    "U3"  = "닉네임/이메일 중복 체크는 서비스단에서 처리한다.`n회원가입 전 이메일 인증 코드 발송이 필요하다. (POST /api/v1/auth/email/code/)`n회원가입 후 온보딩 선호 저장은 PUT /api/v1/preferences/me/ 한 번으로 처리한다."

    "H4"  = $authHeaderJsonCsrf
    "M4"  = $jsonMessageSchema
    "N4"  = $loginSuccessExample
    "P4"  = (Format-ErrorExamples @("INVALID_CREDENTIALS", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q4"  = (Format-StatusCodes 200, 401, 403)
    "U4"  = "access_token, refresh_token을 HttpOnly 쿠키로 발급한다.`ncsrftoken 쿠키도 함께 발급한다.`n로그인 전에 GET /api/v1/auth/csrf/ 호출이 필요하다.`n프론트는 access_token을 직접 저장하지 않고 쿠키 기반으로 인증 상태를 처리한다."

    "H5"  = $csrfHeader
    "P5"  = (Format-ErrorExamples @("REFRESH_TOKEN_MISSING", "INVALID_REFRESH_TOKEN", "CSRF_FAILED"))
    "Q5"  = (Format-StatusCodes 200, 400, 401, 403)
    "U5"  = "refresh_token 쿠키를 기준으로 로그아웃 처리한다.`nrefresh_token을 블랙리스트 처리하고 access_token, refresh_token 쿠키를 만료시킨다."

    "F6"  = "Y"
    "H6"  = $csrfHeader
    "M6"  = $jsonMessageSchema
    "N6"  = $refreshSuccessExample
    "P6"  = (Format-ErrorExamples @("REFRESH_TOKEN_MISSING", "INVALID_REFRESH_TOKEN", "REFRESH_TOKEN_EXPIRED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q6"  = (Format-StatusCodes 200, 400, 401, 403)
    "U6"  = "refresh_token 쿠키를 검증한 뒤 access_token을 재발급한다.`nrefresh token rotation을 적용하며 새 refresh_token 쿠키도 함께 재발급한다.`ncsrftoken 쿠키도 다시 발급한다."

    "K7"  = @'
{
  "email": "string",
  "purpose": "signup | password_reset"
}
'@
    "L7"  = @'
{
  "email": "user@example.com",
  "purpose": "signup"
}
'@
    "U7"  = "인증 코드는 이메일로 발송되며 유효시간은 5분이다.`npurpose로 signup/password_reset을 구분한다."

    "P8"  = (Format-ErrorExamples @("VALIDATION_ERROR", "INVALID_CODE", "CODE_EXPIRED", "SOCIAL_USER_ONLY", "ACCOUNT_DEACTIVATED", "TOO_MANY_REQUESTS"))
    "Q8"  = (Format-StatusCodes 200, 400, 401, 429)
    "U8"  = "비밀번호 재설정 전 이메일 인증 코드 발송이 필요하다.`nPOST /api/v1/auth/email/code/ 호출 시 purpose=password_reset을 사용한다."

    "B9"  = "/api/v1/users/me/verify-password/"
    "C9"  = "/api/v1/users/me/verify-password/"
    "H9"  = $authHeaderJsonCsrf
    "P9"  = (Format-ErrorExamples @("SOCIAL_USER_ONLY", "INVALID_PASSWORD", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q9"  = (Format-StatusCodes 200, 400, 401, 403)
    "U9"  = "현재 비밀번호 일치 여부를 검증한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "A10" = "인증"
    "B10" = "/api/v1/auth/csrf/"
    "C10" = "/api/v1/auth/csrf/"
    "D10" = "GET"
    "E10" = "CSRF 토큰 발급"
    "F10" = "N"
    "K10" = ""
    "L10" = ""
    "M10" = $csrfSuccessSchema
    "N10" = $csrfSuccessExample
    "P10" = ""
    "Q10" = (Format-StatusCodes 200)
    "U10" = "csrftoken 쿠키를 발급한다.`n로그인/로그아웃/리프레시/수정 요청 전에 사용한다."

    "H11" = ""
    "P11" = (Format-ErrorExamples @("UNAUTHORIZED", "TOKEN_EXPIRED", "ACCOUNT_DEACTIVATED"))
    "Q11" = (Format-StatusCodes 200, 401)
    "U11" = "HttpOnly access_token 쿠키 기반으로 현재 인증 사용자를 조회한다.`n앱 초기 진입 시 로그인 상태 복원용으로 사용한다."

    "M13" = "302 Redirect`nSet-Cookie: access_token, refresh_token, csrftoken`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_new_user=true|false"
    "N13" = "302 Redirect`nSet-Cookie: access_token=...; HttpOnly`nSet-Cookie: refresh_token=...; HttpOnly`nSet-Cookie: csrftoken=...`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_new_user=false"
    "P13" = "실패 시 프론트 callback URL로 redirect한다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=INVALID_STATE&error_description=유효하지 않은 state 파라미터입니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=OAUTH_CALLBACK_ERROR&error_description=카카오 인증에 실패했습니다."
    "Q13" = (Format-StatusCodes 302)
    "U13" = "OAuth 성공 시 프론트 callback URL로 redirect한다.`naccess_token, refresh_token을 HttpOnly 쿠키로 설정하고 csrftoken 쿠키도 함께 발급한다.`n프론트 callback에는 토큰을 직접 전달하지 않고 is_new_user만 query parameter로 넘긴다."

    "B14" = "/api/v1/auth/discord/login/"
    "C14" = "/api/v1/auth/discord/login/"
    "E14" = "디스코드 로그인 URL 생성"

    "B15" = "/api/v1/auth/discord/callback/"
    "C15" = "/api/v1/auth/discord/callback/"
    "E15" = "디스코드 로그인 콜백"
    "M15" = "302 Redirect`nSet-Cookie: access_token, refresh_token, csrftoken`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_new_user=true|false"
    "N15" = "302 Redirect`nSet-Cookie: access_token=...; HttpOnly`nSet-Cookie: refresh_token=...; HttpOnly`nSet-Cookie: csrftoken=...`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_new_user=false"
    "P15" = "실패 시 프론트 callback URL로 redirect한다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=INVALID_STATE&error_description=유효하지 않은 state 파라미터입니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=DISCORD_OAUTH_CALLBACK_ERROR&error_description=디스코드 인증에 실패했습니다."
    "Q15" = (Format-StatusCodes 302)
    "U15" = "OAuth 성공 시 프론트 callback URL로 redirect한다.`naccess_token, refresh_token을 HttpOnly 쿠키로 설정하고 csrftoken 쿠키도 함께 발급한다.`n프론트 callback에는 토큰을 직접 전달하지 않고 is_new_user만 query parameter로 넘긴다."

    "H16" = ""
    "P16" = (Format-ErrorExamples @("UNAUTHORIZED", "TOKEN_EXPIRED", "ACCOUNT_DEACTIVATED"))
    "Q16" = (Format-StatusCodes 200, 401)
    "U16" = "풀 프로필 조회용 API이다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H17" = $authHeaderJsonCsrf
    "K17" = @'
{
  "nickname": "string (optional)",
  "birth_date": "date (optional, YYYY-MM-DD)",
  "new_password": "string (optional)"
}
'@
    "L17" = @'
{
  "nickname": "newgamer",
  "new_password": "NewPassw0rd!"
}
'@
    "P17" = (Format-ErrorExamples @("VALIDATION_ERROR", "NICKNAME_ALREADY_EXISTS", "SOCIAL_USER_ONLY", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q17" = (Format-StatusCodes 200, 400, 401, 403, 409)
    "U17" = "미전달 필드는 기존 값을 유지한다.`nnickname, birth_date 수정과 new_password 변경을 동일 API에서 처리한다.`n비밀번호 변경 전 검증은 POST /api/v1/users/me/verify-password/ 에서 선행한다.`n비밀번호 변경 시 기존 refresh token 세션은 모두 무효화된다."

    "H18" = $csrfHeader
    "P18" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q18" = (Format-StatusCodes 200, 401, 403)
    "U18" = "계정을 soft delete 처리하고 deleted_at을 기록한다.`n탈퇴 시 기존 refresh token은 모두 무효화된다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "B19" = "/api/v1/auth/restore/"
    "C19" = "/api/v1/auth/restore/"
    "U19" = "탈퇴 후 7일 이내 계정만 복구할 수 있다.`n복구 성공 시 deleted_at을 제거하고 is_active를 true로 복구한다.`n복구 시 기존 refresh token은 모두 무효화된다."

    "P20" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q20" = (Format-StatusCodes 200, 401)
    "U20" = "최근 검색어는 Redis List 기반으로 저장한다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H21" = $csrfHeader
    "P21" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q21" = (Format-StatusCodes 200, 401, 403)
    "U21" = "최근 검색어를 전체 삭제한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H22" = $csrfHeader
    "P22" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "SEARCH_KEYWORD_NOT_FOUND", "CSRF_FAILED"))
    "Q22" = (Format-StatusCodes 200, 401, 403, 404)
    "U22" = "특정 최근 검색어 1건을 삭제한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H23" = $multipartCsrfHeader
    "P23" = (Format-ErrorExamples @("INVALID_FILE_TYPE", "FILE_TOO_LARGE", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q23" = (Format-StatusCodes 200, 400, 401, 403)
    "U23" = "프론트가 이미지를 백엔드로 직접 업로드하면, 백엔드가 리사이즈 후 S3에 업로드한다.`n허용 확장자: jpg, jpeg, png, webp`n최대 파일 크기: 5MB"

    "H24" = $csrfHeader
    "P24" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q24" = (Format-StatusCodes 200, 401, 403)
    "U24" = "profile_img_url을 null로 변경하고 기존 S3 이미지를 삭제한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H25" = ""
    "M25" = "302 Redirect"
    "N25" = "Location: {BBATON_AUTH_URL}"
    "P25" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q25" = (Format-StatusCodes 302, 401)
    "U25" = "로그인된 사용자의 성인 인증을 시작하고 비바톤 인증 URL로 redirect한다.`n카카오/디스코드 login 엔드포인트와 유사하게 외부 인증 URL로 이동하는 패턴이다."

    "M26" = "302 Redirect`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_adult_verified=true&adult_verified_at=...&expires_at=..."
    "N26" = "302 Redirect`nLocation: {FRONTEND_DOMAIN}/auth/callback?is_adult_verified=true&adult_verified_at=2026-03-24T12:34:56+09:00&expires_at=2026-03-25T12:34:56+09:00"
    "P26" = "실패 시 프론트 callback URL로 redirect한다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=INVALID_STATE&error_description=유효하지 않은 state 파라미터입니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=ADULT_VERIFICATION_CALLBACK_ERROR&error_description=비바톤 인증에 실패했습니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=UNDERAGE&error_description=만 18세 미만은 성인 인증을 완료할 수 없습니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=ALREADY_VERIFIED&error_description=이미 성인 인증이 완료된 계정입니다.`nLocation: {FRONTEND_DOMAIN}/auth/callback?error=VERIFICATION_ALREADY_USED&error_description=이미 사용된 인증 정보입니다. (provider_uid 중복)"
    "Q26" = (Format-StatusCodes 302, 400)
    "U26" = "비바톤 콜백을 처리한 뒤 성공/실패 모두 프론트 callback URL로 redirect한다."

    "H27" = ""
    "P27" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q27" = (Format-StatusCodes 200, 401)
    "U27" = "현재 성인 인증 상태와 만료 시각을 조회한다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "U28" = "게임 목록은 IGDB 기반으로 조회된다.`ngenre_ids, platform_ids, tag_ids는 서버 메타데이터 id를 사용한다.`n프론트는 /api/v1/games/genres/, /platforms/, /tags/ 응답의 id를 사용해야 한다.`n성인 비인증 사용자는 성인 게임을 목록에서 제외한다."
    "U29" = "게임 상세는 IGDB 기반으로 조회한다.`n성인 게임은 성인 인증 상태에 따라 접근이 제한된다.`n조회 자체로 interaction log를 자동 기록하지 않으며, view 기록은 POST /api/v1/interactions/view/ 로 별도 전송한다."
    "U30" = "유사도는 내부 유사도 테이블을 기반으로 계산하고, 게임 상세 정보는 외부 게임 데이터를 hydrate해서 반환한다."

    "B31" = "/api/v1/games/genres/"
    "C31" = "/api/v1/games/genres/"
    "U31" = "장르 메타데이터 목록 API이다.`n프론트는 장르 ID를 하드코딩하지 않고 이 API 응답의 id를 사용해야 한다.`n데이터가 없으면 빈 리스트를 반환한다."

    "B32" = "/api/v1/games/platforms/"
    "C32" = "/api/v1/games/platforms/"
    "U32" = "플랫폼 메타데이터 목록 API이다.`n프론트는 플랫폼 ID를 하드코딩하지 않고 이 API 응답의 id를 사용해야 한다.`n데이터가 없으면 빈 리스트를 반환한다."

    "B33" = "/api/v1/games/tags/"
    "C33" = "/api/v1/games/tags/"
    "U33" = "태그 메타데이터 목록 API이다.`n프론트는 태그 ID를 하드코딩하지 않고 이 API 응답의 id를 사용해야 한다.`n현재 서비스 기준 태그 목록을 전체 반환한다."

    "H34" = ""
    "P34" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q34" = (Format-StatusCodes 200, 401)
    "U34" = "저장된 장르/플랫폼/태그 선호를 조회한다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H35" = $authHeaderJsonCsrf
    "P35" = (Format-ErrorExamples @("PREFERENCE_FIELDS_REQUIRED", "INVALID_GENRE_ID", "INVALID_PLATFORM_ID", "INVALID_TAG_ID", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED"))
    "Q35" = (Format-StatusCodes 200, 400, 401, 403)
    "U35" = "기존 선호 정보를 입력된 리스트 기준으로 전체 교체한다.`n온보딩 포함 전체 선호 저장은 이 API 한 번으로 처리한다."

    "H36" = $authHeaderJsonCsrf
    "P36" = (Format-ErrorExamples @("INVALID_REACTION", "REACTION_DATA_REQUIRED", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED", "GAME_NOT_FOUND"))
    "Q36" = (Format-StatusCodes 200, 400, 401, 403, 404)
    "U36" = "특정 게임에 대한 저장 상태 및 반응 값을 수정한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H37" = ""
    "P37" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q37" = (Format-StatusCodes 200, 401)
    "U37" = "찜한 게임 목록을 조회한다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H38" = ""
    "P38" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q38" = (Format-StatusCodes 200, 401)
    "U38" = "유저의 게임 취향 점수 목록을 조회한다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H39" = $authHeaderJsonCsrf
    "P39" = (Format-ErrorExamples @("GAME_ID_OR_SOURCE_MISSING", "INVALID_SOURCE", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED", "INTERACTION_TYPE_NOT_FOUND", "SOURCE_NOT_FOUND"))
    "Q39" = (Format-StatusCodes 200, 201, 400, 401, 403, 404)
    "U39" = "게임 상세 view 로그를 기록한다.`n중복/쿨다운으로 새 로그를 만들지 않은 경우 200 OK를 반환하고, 신규 생성 시 201 Created를 반환한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H40" = $authHeaderJsonCsrf
    "P40" = (Format-ErrorExamples @("SEARCH_QUERY_MISSING", "GAME_ID_OR_SOURCE_MISSING", "INVALID_SOURCE", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED", "INTERACTION_TYPE_NOT_FOUND", "SOURCE_NOT_FOUND"))
    "Q40" = (Format-StatusCodes 200, 201, 400, 401, 403, 404)
    "U40" = "검색 인터랙션 로그를 기록한다.`n중복/쿨다운으로 새 로그를 만들지 않은 경우 200 OK를 반환하고, 신규 생성 시 201 Created를 반환한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H41" = $authHeaderJsonCsrf
    "P41" = (Format-ErrorExamples @("GAME_ID_OR_STORE_ID_MISSING", "GAME_ID_OR_SOURCE_MISSING", "INVALID_SOURCE", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED", "CSRF_FAILED", "STORE_NOT_FOUND", "INTERACTION_TYPE_NOT_FOUND", "SOURCE_NOT_FOUND"))
    "Q41" = (Format-StatusCodes 200, 201, 400, 401, 403, 404)
    "U41" = "스토어 클릭 인터랙션 로그를 기록한다.`n중복/쿨다운으로 새 로그를 만들지 않은 경우 200 OK를 반환하고, 신규 생성 시 201 Created를 반환한다.`nHttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H42" = ""
    "P42" = (Format-ErrorExamples @("RECOMMENDATION_NOT_READY", "UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q42" = (Format-StatusCodes 200, 202, 401)
    "U42" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "H43" = ""
    "P43" = (Format-ErrorExamples @("UNAUTHORIZED", "ACCOUNT_DEACTIVATED"))
    "Q43" = (Format-StatusCodes 200, 401)
    "U43" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B45" = "/api/v1/admin/recommendation-jobs/"
    "C45" = "/api/v1/admin/recommendation-jobs/"
    "H45" = ""
    "P45" = (Format-ErrorExamples @("INVALID_QUERY_PARAM", "UNAUTHORIZED", "FORBIDDEN"))
    "Q45" = (Format-StatusCodes 200, 400, 401, 403)
    "U45" = "is_staff=true 유저만 접근 가능하다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "B46" = "/api/v1/admin/recommendation-jobs/{job_id}/"
    "C46" = "/api/v1/admin/recommendation-jobs/{job_id}/"
    "H46" = ""
    "P46" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN", "JOB_NOT_FOUND"))
    "Q46" = (Format-StatusCodes 200, 401, 403, 404)
    "U46" = "is_staff=true 유저만 접근 가능하다.`nHttpOnly 쿠키 기반 인증을 사용한다."

    "H47" = $authHeaderJsonCsrf
    "P47" = (Format-ErrorExamples @("JOB_TYPE_MISSING", "UNAUTHORIZED", "FORBIDDEN", "CSRF_FAILED", "JOB_ALREADY_RUNNING"))
    "Q47" = (Format-StatusCodes 201, 400, 401, 403, 409)
    "U47" = "is_staff=true 유저만 접근 가능하다.`ntarget_user_id=null이면 전체 유저 대상 실행이다.`n동일 job_type + target_user_id 기준 pending/running 작업이 있으면 JOB_ALREADY_RUNNING을 반환한다."

    "H48" = ""
    "P48" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN"))
    "Q48" = (Format-StatusCodes 200, 401, 403)
    "U48" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B49" = "/api/v1/admin/interaction-weight-rules/{interaction_type}/"
    "C49" = "/api/v1/admin/interaction-weight-rules/{interaction_type}/"
    "H49" = $authHeaderJsonCsrf
    "P49" = (Format-ErrorExamples @("BASE_WEIGHT_INVALID", "UNAUTHORIZED", "FORBIDDEN", "CSRF_FAILED", "INTERACTION_TYPE_NOT_FOUND"))
    "Q49" = (Format-StatusCodes 200, 400, 401, 403, 404)
    "U49" = "HttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "H50" = ""
    "P50" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN"))
    "Q50" = (Format-StatusCodes 200, 401, 403)
    "U50" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "H51" = $authHeaderJsonCsrf
    "P51" = (Format-ErrorExamples @("MULTIPLIER_INVALID", "UNAUTHORIZED", "FORBIDDEN", "CSRF_FAILED", "SOURCE_NOT_FOUND"))
    "Q51" = (Format-StatusCodes 200, 400, 401, 403, 404)
    "U51" = "HttpOnly 쿠키 기반 인증이며 unsafe 요청이므로 X-CSRFToken 헤더가 필요하다."

    "B53" = "/api/v1/admin/users/dashboard/"
    "C53" = "/api/v1/admin/users/dashboard/"
    "H53" = ""
    "P53" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN"))
    "Q53" = (Format-StatusCodes 200, 401, 403)
    "U53" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B54" = "/api/v1/admin/users/"
    "C54" = "/api/v1/admin/users/"
    "H54" = ""
    "P54" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN"))
    "Q54" = (Format-StatusCodes 200, 401, 403)
    "U54" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B55" = "/api/v1/admin/users/{user_id}/"
    "C55" = "/api/v1/admin/users/{user_id}/"
    "H55" = ""
    "P55" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN", "USER_NOT_FOUND"))
    "Q55" = (Format-StatusCodes 200, 401, 403, 404)
    "U55" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B56" = "/api/v1/admin/users/{user_id}/"
    "C56" = "/api/v1/admin/users/{user_id}/"
    "H56" = $authHeaderJsonCsrf
    "P56" = (Format-ErrorExamples @("VALIDATION_ERROR", "UNAUTHORIZED", "FORBIDDEN", "CSRF_FAILED", "USER_NOT_FOUND"))
    "Q56" = (Format-StatusCodes 200, 400, 401, 403, 404)
    "U56" = "is_active 값을 변경한다.`n재활성화 시 deleted_at도 함께 정리하고 기존 refresh token은 모두 무효화한다."

    "B57" = "/api/v1/admin/users/{user_id}/recommendations/"
    "C57" = "/api/v1/admin/users/{user_id}/recommendations/"
    "H57" = ""
    "P57" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN", "USER_NOT_FOUND"))
    "Q57" = (Format-StatusCodes 200, 401, 403, 404)
    "U57" = "HttpOnly 쿠키 기반 인증을 사용한다."

    "B58" = "/api/v1/admin/users/{user_id}/interactions/"
    "C58" = "/api/v1/admin/users/{user_id}/interactions/"
    "H58" = ""
    "P58" = (Format-ErrorExamples @("UNAUTHORIZED", "FORBIDDEN", "USER_NOT_FOUND"))
    "Q58" = (Format-StatusCodes 200, 401, 403, 404)
    "U58" = "특정 유저의 interaction log를 페이지네이션 조회한다.`nHttpOnly 쿠키 기반 인증을 사용한다."
}

$clearCells = @(
    "H10"
)

$source = (Resolve-Path -LiteralPath $SourcePath).Path
$destinationDirectory = Split-Path -Path $DestinationPath -Parent
if (-not (Test-Path -LiteralPath $destinationDirectory)) {
    New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
}

$tempRoot = Join-Path $env:TEMP ("api_spec_patch_" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($source, $tempRoot)

    $sheetPath = Join-Path $tempRoot "xl\worksheets\sheet1.xml"
    [xml]$sheetXml = Get-Content -LiteralPath $sheetPath -Encoding utf8
    $nsMgr = New-Object System.Xml.XmlNamespaceManager($sheetXml.NameTable)
    $nsMgr.AddNamespace("x", $MainNs)

    foreach ($cellRef in $clearCells) {
        Clear-CellValue -SheetXml $sheetXml -NsMgr $nsMgr -CellReference $cellRef
    }

    foreach ($entry in $updates.GetEnumerator()) {
        Set-CellText -SheetXml $sheetXml -NsMgr $nsMgr -CellReference $entry.Key -Text ([string]$entry.Value)
    }

    foreach ($rowNumber in @(44, 52)) {
        Clear-RowRange -SheetXml $sheetXml -NsMgr $nsMgr -RowNumber $rowNumber -ColumnsToClear $Columns
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($sheetPath, $sheetXml.OuterXml, $utf8NoBom)

    if (Test-Path -LiteralPath $DestinationPath) {
        Remove-Item -LiteralPath $DestinationPath -Force
    }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($tempRoot, $DestinationPath)
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
